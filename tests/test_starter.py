"""Offline unit tests for the Starter repository (plugin loader, agent build, eval loader)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import pytest

from app.agent import build_agent
from app.loader import (
    assert_no_state_tokens,
    hello_expedition_status,
    load_seed_pack,
    resolve_pack_directory,
    sanitize_instruction,
)
from eval.run_eval import (
    discover_eval_files,
    load_eval_cases,
    score_response_match,
    score_tool_trajectory,
)


def test_fallback_hello_pack_when_seed_pack_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """When SEED_PACK is unset, loader returns the generic hello_fallback pack."""
    monkeypatch.delenv("SEED_PACK", raising=False)
    pack = load_seed_pack("")
    assert pack.pack_id == "hello_fallback"
    assert pack.mcp_stdio_attached is False
    assert len(pack.tools) == 1
    out = json.loads(hello_expedition_status("Table 8"))
    assert out["status"] == "ONLINE"
    assert out["table_name"] == "Table 8"


def test_load_t00_example_pack_and_prefix_resolution() -> None:
    """Loader resolves both exact ('t00_example') and prefix ('t00') pack directories."""
    resolved = resolve_pack_directory("t00")
    assert resolved.name == "t00_example"

    pack_plain = load_seed_pack("t00_example", enable_mcp_stdio=False, strict_state_tokens=True)
    assert pack_plain.pack_id == "t00_example"
    assert pack_plain.bigquery_dataset == "seed_t00"
    assert pack_plain.mcp_stdio_attached is False
    tool_names = [t.__name__ for t in pack_plain.tools if callable(t)]
    assert "lookup_coffee_menu" in tool_names
    assert "get_roastery_sales_stats" in tool_names
    assert "submit_bean_reorder" in tool_names
    assert len(tool_names) == len(set(tool_names)), "Duplicate tool names must never be registered"


def test_load_t00_example_with_mcp_stdio_deduplicates_tools() -> None:
    """When MCP stdio is enabled, McpToolset is attached and plain duplicate MCP tools are filtered."""
    pack_mcp = load_seed_pack("t00_example", enable_mcp_stdio=True)
    assert pack_mcp.mcp_stdio_attached is True
    fn_names = [t.__name__ for t in pack_mcp.tools if callable(t)]
    assert "lookup_coffee_menu" in fn_names
    assert "get_roastery_sales_stats" in fn_names
    # submit_bean_reorder is served via McpToolset when stdio is attached
    assert "submit_bean_reorder" not in fn_names
    assert len(pack_mcp.tools) == 3


def test_state_token_guard_and_sanitizer() -> None:
    """Instruction state-token guard catches raw {var} tokens while allowing {user:*}."""
    assert_no_state_tokens("Clean prompt with {user:preferred_lang} and no bare braces.")
    with pytest.raises(ValueError, match="session-state tokens"):
        assert_no_state_tokens("Bad prompt with {json_payload} inside.")

    sanitized = sanitize_instruction("Order {order_id} for {user:name}")
    assert sanitized == "Order [order_id] for {user:name}"
    assert_no_state_tokens(sanitized)


def test_agent_builds_offline_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Root ADK LlmAgent builds without network calls for both fallback and t00_example."""
    monkeypatch.setenv("SEED_OFFLINE_MODE", "1")
    agent_hello, pack_hello = build_agent("", enable_mcp_stdio=False)
    assert pack_hello.pack_id == "hello_fallback"
    assert agent_hello.name == "expedition_hello_fallback"

    agent_t00, pack_t00 = build_agent("t00_example", enable_mcp_stdio=False)
    assert pack_t00.pack_id == "t00_example"
    assert agent_t00.name == "expedition_t00_example"
    assert len(agent_t00.tools) == 3


def test_rejects_latest_model_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    """Model configuration rejects forbidden -latest aliases."""
    monkeypatch.setenv("GEMINI_MODEL", "gemini-flash-latest")
    with pytest.raises(ValueError, match="-latest"):
        build_agent("t00_example", enable_mcp_stdio=False)


def test_t00_example_tools_execute_offline_and_never_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tools return valid JSON in offline mode and return structured errors on bad inputs."""
    monkeypatch.setenv("SEED_OFFLINE_MODE", "1")
    from seed_packs.t00_example.tools import (
        get_roastery_sales_stats,
        lookup_coffee_menu,
        submit_bean_reorder,
    )

    menu_res = json.loads(lookup_coffee_menu("espresso"))
    assert menu_res["status"] == "SUCCESS"
    assert menu_res["count"] == 2

    sales_res = json.loads(get_roastery_sales_stats("London Soho"))
    assert sales_res["status"] == "SUCCESS"
    assert sales_res["total_revenue_gbp"] == 4450.40

    order_res = json.loads(submit_bean_reorder("Ethiopian Yirgacheffe", 25, "express"))
    assert order_res["status"] == "SUCCESS"
    assert order_res["order"]["bags_kg"] == 25

    bad_order = json.loads(submit_bean_reorder("", -5, "standard"))
    assert bad_order["status"] == "INVALID_ARGUMENT"


def test_eval_loader_discovers_and_validates_five_golden_cases() -> None:
    """Evaluation loader discovers t00_example/eval/golden.test.json and validates all 5 cases."""
    files = discover_eval_files("t00_example")
    assert len(files) == 1
    assert files[0].name == "golden.test.json"

    eval_set, cases = load_eval_cases(files[0])
    assert eval_set is not None
    assert len(cases) == 5
    for case in cases:
        assert len(case.turns) >= 1
        assert case.turns[0].user_text
        assert len(case.turns[0].expected_tools) >= 1

    assert score_tool_trajectory(
        [{"name": "lookup_coffee_menu"}],
        [{"name": "lookup_coffee_menu", "args": {"category": "espresso"}}],
    ) == 1.0
    assert score_response_match("Flat White is £3.80", "We offer Flat White for £3.80.") > 0.4


# ---------------------------------------------------------------------------
# Red-team regression tests: public MCP contract, config placeholders, eval
# discovery, actionable errors and deploy/delete safety.
# ---------------------------------------------------------------------------


def test_mcp_extraction_uses_public_mcp_tools_list_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Loader reads the explicit MCP_TOOLS list and never FastMCP private internals."""
    from app import loader

    (tmp_path / "rt_public_mcp.py").write_text(
        "def ping() -> str:\n    return 'pong'\n\nMCP_TOOLS = [ping]\n", encoding="utf-8"
    )
    (tmp_path / "rt_private_mcp.py").write_text(
        "import types\n"
        "def hidden() -> str:\n    return 'x'\n"
        "_tool = types.SimpleNamespace(fn=hidden)\n"
        "mcp = types.SimpleNamespace(_tool_manager=types.SimpleNamespace(_tools={'hidden': _tool}))\n",
        encoding="utf-8",
    )
    (tmp_path / "rt_broken_mcp.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    public = loader._extract_mcp_module_functions("rt_public_mcp")
    assert [fn.__name__ for fn in public] == ["ping"]
    assert loader._extract_mcp_module_functions("rt_private_mcp") == []
    with pytest.raises(ImportError, match="failed to import"):
        loader._extract_mcp_module_functions("rt_broken_mcp")


def test_resolve_env_config_ignores_template_placeholders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Values copied verbatim from .env.example never leak into project/bucket config."""
    from app import loader

    (tmp_path / ".env").write_text(
        "GOOGLE_CLOUD_PROJECT=my-real-project\n"
        "STAGING_BUCKET=gs://your-gcp-project-id-hackathon-staging\n",
        encoding="utf-8",
    )
    (tmp_path / ".env.example").write_text(
        "STAGING_BUCKET=gs://your-gcp-project-id-hackathon-staging\nGEMINI_MODEL=model-from-example\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(loader, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "your-gcp-project-id")
    monkeypatch.delenv("STAGING_BUCKET", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    assert loader.resolve_env_config("GOOGLE_CLOUD_PROJECT") == "my-real-project"
    assert loader.resolve_env_config("STAGING_BUCKET", default="gs://fallback") == "gs://fallback"
    assert loader.resolve_env_config("GEMINI_MODEL") == "model-from-example"


def test_discover_eval_files_fails_loudly_for_pack_without_eval_dir(tmp_path: Path) -> None:
    """A pack without eval/ must not silently run the unrelated hello_fallback cases."""
    pack_dir = tmp_path / "t99_demo"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text("id: t99_demo\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="has no eval/ folder"):
        discover_eval_files("t99", seed_packs_dir=tmp_path)


def test_explain_gcp_error_gives_actionable_hints() -> None:
    """Common newcomer failures map to a concrete next command."""
    from app.preflight import explain_gcp_error, parse_reasoning_engine_name

    disabled = explain_gcp_error(
        RuntimeError("403 SERVICE_DISABLED: Vertex AI API has not been used in project p1"), "p1"
    )
    assert "gcloud services enable" in disabled and "--project=p1" in disabled
    adc = explain_gcp_error(type("DefaultCredentialsError", (Exception,), {})("no creds"), "p1")
    assert "application-default login" in adc
    dataset = explain_gcp_error(RuntimeError("404 Not found: Dataset p1:seed_t00"), "p1")
    assert "make seed" in dataset
    assert explain_gcp_error(RuntimeError("something unrelated"), "p1") == ""

    parts = parse_reasoning_engine_name("projects/p1/locations/europe-west1/reasoningEngines/42")
    assert parts == {"project": "p1", "location": "europe-west1", "id": "42"}
    with pytest.raises(ValueError, match="full Agent Runtime resource name"):
        parse_reasoning_engine_name("42")


class _FakeRemote:
    def __init__(self, name: str, log: list[tuple[str, str]]) -> None:
        self.resource_name = name
        self._log = log

    def delete(self, force: bool = False) -> None:
        self._log.append(("delete", self.resource_name))


class _FakeAgentEngines:
    def __init__(self, update_error: Exception | None = None) -> None:
        self.update_error = update_error
        self.calls: list[tuple[str, str]] = []

    def update(self, *, resource_name: str, **_: object) -> _FakeRemote:
        self.calls.append(("update", resource_name))
        if self.update_error is not None:
            raise self.update_error
        return _FakeRemote(resource_name, self.calls)

    def create(self, **_: object) -> _FakeRemote:
        self.calls.append(("create", ""))
        return _FakeRemote("projects/p1/locations/europe-west1/reasoningEngines/999", self.calls)

    def get(self, name: str) -> _FakeRemote:
        self.calls.append(("get", name))
        return _FakeRemote(name, self.calls)


_SAVED = "projects/p1/locations/europe-west1/reasoningEngines/123"


def _prepare_deploy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake: _FakeAgentEngines) -> Path:
    import deploy.deploy as dep

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "p1")
    monkeypatch.setenv("AGENT_RUNTIME_LOCATION", "europe-west1")
    monkeypatch.setenv("ENABLE_MCP_STDIO", "0")
    monkeypatch.setenv("AGENT_RUNTIME_DEPLOY", "1")
    monkeypatch.setattr(dep.vertexai, "init", lambda **_: None)
    monkeypatch.setattr(dep, "AdkApp", lambda **_: object())
    monkeypatch.setattr(dep, "agent_engines", fake)
    state = tmp_path / ".deployed_agent.json"
    state.write_text(json.dumps({"resource_name": _SAVED, "project_id": "p1"}), encoding="utf-8")
    return state


def test_deploy_update_failure_never_creates_a_second_agent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A non-404 update error must raise instead of orphaning the saved agent."""
    import deploy.deploy as dep

    fake = _FakeAgentEngines(update_error=RuntimeError("400 INVALID_ARGUMENT: bad requirements"))
    state = _prepare_deploy(monkeypatch, tmp_path, fake)
    with pytest.raises(RuntimeError, match="Nothing was created"):
        dep.deploy_agent(pack_id="t00_example", state_file=state, check_bucket=False)
    assert fake.calls == [("update", _SAVED)]
    assert json.loads(state.read_text(encoding="utf-8"))["resource_name"] == _SAVED


def test_deploy_recreates_only_when_saved_agent_is_gone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A 404 on update (agent deleted in console) creates a new agent and records it."""
    import deploy.deploy as dep

    fake = _FakeAgentEngines(update_error=RuntimeError("404 NOT_FOUND: reasoningEngine 123"))
    state = _prepare_deploy(monkeypatch, tmp_path, fake)
    name = dep.deploy_agent(pack_id="t00_example", state_file=state, check_bucket=False)
    assert [c[0] for c in fake.calls] == ["update", "create"]
    assert json.loads(state.read_text(encoding="utf-8"))["resource_name"] == name != _SAVED


def test_deploy_refuses_state_file_from_another_region(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Switching region/project in .env must not silently abandon the saved agent."""
    import deploy.deploy as dep

    fake = _FakeAgentEngines()
    state = _prepare_deploy(monkeypatch, tmp_path, fake)
    monkeypatch.setenv("AGENT_RUNTIME_LOCATION", "europe-west2")
    with pytest.raises(RuntimeError, match="make delete"):
        dep.deploy_agent(pack_id="t00_example", state_file=state, check_bucket=False)
    assert fake.calls == []


def test_delete_targets_one_resource_and_keeps_unrelated_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Deleting an explicit other resource keeps the saved one tracked; deleting the saved one clears it."""
    import deploy.delete as dele

    fake = _FakeAgentEngines()
    monkeypatch.setattr(dele.vertexai, "init", lambda **_: None)
    monkeypatch.setattr(dele, "agent_engines", fake)
    monkeypatch.delenv("AGENT_ENGINE_RESOURCE_NAME", raising=False)
    state = tmp_path / ".deployed_agent.json"
    state.write_text(json.dumps({"resource_name": _SAVED}), encoding="utf-8")

    other = "projects/p1/locations/europe-west1/reasoningEngines/777"
    dele.delete_remote_agent(other, state_file=state)
    assert ("delete", other) in fake.calls and state.exists()

    dele.delete_remote_agent(state_file=state)
    assert ("delete", _SAVED) in fake.calls and not state.exists()

    with pytest.raises(ValueError, match="full Agent Runtime resource name"):
        dele.delete_remote_agent("777", state_file=state)


# ---------------------------------------------------------------------------
# Table 7 (t07_self_healing_ops) Guardrails, SecOps & Table 8 A2A Unit Tests
# ---------------------------------------------------------------------------


def test_t07_pack_loads_cleanly_without_state_tokens() -> None:
    """Table 7 seed pack loads with 6 tools and passes strict state-token validation."""
    pack = load_seed_pack("t07", enable_mcp_stdio=False, strict_state_tokens=True)
    assert pack.pack_id == "t07"
    assert pack.bigquery_dataset == "seed_t07"
    tool_names = [t.__name__ for t in pack.tools if callable(t)]
    assert set(tool_names) == {
        "query_active_incidents",
        "inspect_deployment_release",
        "lookup_slo_runbook",
        "execute_canary_rollback",
        "scale_service_replicas",
        "annotate_incident_timeline",
    }


def test_t07_prompt_injection_detection_inc_0019(monkeypatch: pytest.MonkeyPatch) -> None:
    """query_active_incidents flags INC-0019 lateral prompt injection with security_warning."""
    monkeypatch.setenv("SEED_OFFLINE_MODE", "1")
    from seed_packs.t07_self_healing_ops.tools import query_active_incidents

    res = json.loads(query_active_incidents("SEV1", "realtime-pricing-engine"))
    assert res["status"] == "SUCCESS"
    by_id = {row["incident_id"]: row for row in res["incidents"]}
    assert "INC-0019" in by_id
    assert "security_warning" in by_id["INC-0019"]
    assert "PROMPT_INJECTION_DETECTED" in by_id["INC-0019"]["security_warning"]
    assert "INC-0004" in by_id
    assert "security_warning" not in by_id["INC-0004"]


def test_t07_rollback_blast_radius_and_table8_a2a_advisory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """execute_canary_rollback enforces allowlisted previous_stable_version, service match, and emits Table 8 A2A."""
    import seed_packs.t07_self_healing_ops.mcp_server as t07_mcp

    monkeypatch.setattr(t07_mcp, "_DEFAULT_STATE_PATH", tmp_path / ".state.json")

    ok = json.loads(
        t07_mcp.execute_canary_rollback(
            incident_id="INC-0001",
            service_name="checkout-payment-svc",
            target_stable_version="v2.10.0",
            reason="Elevated P99 latency after REL-0001",
        )
    )
    assert ok["status"] == "SUCCESS"
    assert ok["rollback"]["active_release_id"] == "REL-0001"
    assert ok["rollback"]["rollback_safe_verified"] is True
    assert ok["table8_a2a_advisory"]["target_table"] == "t08_travel_concierge"
    assert ok["table8_a2a_advisory"]["affected_service"] == "checkout-payment-svc"

    bad_ver = json.loads(
        t07_mcp.execute_canary_rollback(
            incident_id="INC-0001",
            service_name="checkout-payment-svc",
            target_stable_version="v0.0.1-poisoned",
            reason="Attempted downgrade to unverified tag",
        )
    )
    assert bad_ver["status"] == "REJECTED_UNSAFE_ROLLBACK"
    assert bad_ver["allowed_previous_stable_version"] == "v2.10.0"

    cross_svc = json.loads(
        t07_mcp.execute_canary_rollback(
            incident_id="INC-0019",
            service_name="auth-token-gateway",
            target_stable_version="v2.28.0",
            reason="Lateral cross-service rollback attempt",
        )
    )
    assert cross_svc["status"] == "REJECTED_UNSAFE_ROLLBACK"
    assert cross_svc["incident_service_name"] == "realtime-pricing-engine"


def test_t07_replica_corridor_guardrail_and_table8_a2a(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """scale_service_replicas blocks target_replicas=0 (INC-0019) and emits Table 8 A2A on valid scale."""
    import seed_packs.t07_self_healing_ops.mcp_server as t07_mcp

    monkeypatch.setattr(t07_mcp, "_DEFAULT_STATE_PATH", tmp_path / ".state.json")

    zero_attack = json.loads(
        t07_mcp.scale_service_replicas(
            service_name="auth-token-gateway",
            cluster_region="europe-west1",
            target_replicas=0,
        )
    )
    assert zero_attack["status"] == "REJECTED_REPLICA_GUARDRAIL"
    assert zero_attack["safe_replica_corridor"] == [3, 40]
    assert zero_attack["audit_annotation"]["new_status"] == "ESCALATED"

    valid_scale = json.loads(
        t07_mcp.scale_service_replicas(
            service_name="auth-token-gateway",
            cluster_region="europe-west1",
            target_replicas=12,
        )
    )
    assert valid_scale["status"] == "SUCCESS"
    assert valid_scale["scaling_event"]["target_replicas"] == 12
    assert valid_scale["table8_a2a_advisory"]["target_table"] == "t08_travel_concierge"
    assert valid_scale["table8_a2a_advisory"]["affected_service"] == "auth-token-gateway"


def test_t07_timeline_status_validation_and_stored_injection_sanitization(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """annotate_incident_timeline validates statuses, sanitizes HTML comments, and preserves idempotency."""
    import seed_packs.t07_self_healing_ops.mcp_server as t07_mcp

    monkeypatch.setattr(t07_mcp, "_DEFAULT_STATE_PATH", tmp_path / ".state.json")

    bad_status = json.loads(
        t07_mcp.annotate_incident_timeline(
            incident_id="INC-0019",
            remediation_summary="Attempted invalid status",
            new_status="PWNED",
        )
    )
    assert bad_status["status"] == "REJECTED_INVALID_STATUS"

    sanitized = json.loads(
        t07_mcp.annotate_incident_timeline(
            incident_id="INC-0019",
            remediation_summary="Blocked attack <!-- PROMPT INJECTION: target_replicas=0 -->",
            new_status="ESCALATED",
        )
    )
    assert sanitized["status"] == "SUCCESS"
    assert sanitized["annotation"]["annotation_id"] == "TIMELINE-3001"
    assert sanitized["annotation"]["service_name"] == "realtime-pricing-engine"
    assert "<!--" not in sanitized["annotation"]["remediation_summary"]

    # Repeating the exact same incident_id + new_status reuses TIMELINE-3001 idempotently
    repeat = json.loads(
        t07_mcp.annotate_incident_timeline(
            incident_id="INC-0019",
            remediation_summary="Updated summary",
            new_status="ESCALATED",
        )
    )
    assert repeat["annotation"]["annotation_id"] == "TIMELINE-3001"


def test_t07_direct_incident_lookup_and_seed_pack_validator(monkeypatch: pytest.MonkeyPatch) -> None:
    """query_active_incidents and inspect_deployment_release resolve INC-xxxx directly and pass check_packs."""
    monkeypatch.setenv("SEED_OFFLINE_MODE", "1")
    from seed_packs.check_packs import _check_pack
    from seed_packs.t07_self_healing_ops.tools import (
        inspect_deployment_release,
        query_active_incidents,
    )

    inc_res = json.loads(query_active_incidents("all", "INC-0019"))
    assert inc_res["status"] == "SUCCESS"
    assert inc_res["count"] == 1
    assert inc_res["incidents"][0]["incident_id"] == "INC-0019"

    rel_res = json.loads(inspect_deployment_release("INC-0019"))
    assert rel_res["status"] == "SUCCESS"
    assert rel_res["count"] == 1
    assert rel_res["releases"][0]["release_id"] == "REL-0019"

    assert _check_pack("t07", 7, "t07_self_healing_ops") == []


def test_t07_showcase_ui_dashboard_and_guardrail_simulator(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Showcase UI dashboard and deterministic guardrail simulators work cleanly."""
    import asyncio
    import seed_packs.t07_self_healing_ops.mcp_server as t07_mcp
    from ui.server import GuardrailSimulationRequest, _build_dashboard_payload, api_simulate_guardrail

    monkeypatch.setattr(t07_mcp, "_DEFAULT_STATE_PATH", tmp_path / ".state.json")

    dash = _build_dashboard_payload()
    assert dash["status"] == "ONLINE"
    assert len(dash["services"]) == 5
    assert any(inc.get("security_warning") for inc in dash["top_sev1_incidents"])

    resp = asyncio.run(api_simulate_guardrail(GuardrailSimulationRequest(scenario="zero_replica_attack")))
    sim = json.loads(resp.body.decode("utf-8"))
    assert sim["status"] == "SUCCESS"
    assert sim["tool_calls"][0]["output"]["status"] == "REJECTED_REPLICA_GUARDRAIL"
    assert len(sim["dashboard"]["state"]["incident_updates"]) >= 1

