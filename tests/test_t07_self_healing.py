"""Unit tests for Table 7: Self-Healing Infrastructure & Security Copilot (t07_self_healing_ops)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import cloudpickle
import pytest

from app.agent import (
    after_tool_callback,
    before_tool_callback,
    create_agent,
    resolve_model_routing_tier,
)
from seed_packs.t07_self_healing_ops import mcp_server, tools


@pytest.fixture(autouse=True)
def _clean_t07_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset Table 7 local state before and after each test and force deterministic CSV fallback."""
    monkeypatch.setenv("SEED_PACK", "t07")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "")
    monkeypatch.setenv("AGENT_ENGINE_PROJECT", "")
    mcp_server.reset_state()
    yield
    mcp_server.reset_state()


class _DummyTool:
    def __init__(self, name: str) -> None:
        self.name = name


def test_t07_agent_cloudpickle_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Root agent with before_tool_callback and after_tool_callback must serialize via cloudpickle."""
    monkeypatch.setenv("SEED_PACK", "t07")
    agent = create_agent()
    payload = cloudpickle.dumps(agent)
    restored = cloudpickle.loads(payload)
    assert restored.name == "expedition_t07"
    assert restored.before_tool_callback is not None
    assert restored.after_tool_callback is not None


def test_model_routing_tier_reads_environment_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Model routing helper must resolve model names strictly from environment variables."""
    monkeypatch.setenv("GEMINI_MODEL", "custom-flash-tier")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "global")
    tier_sev1 = resolve_model_routing_tier(severity="SEV1", injection_detected=True)
    assert tier_sev1["active_model"] == "custom-flash-tier"
    assert tier_sev1["location"] == "global"
    assert tier_sev1["reasoning_budget"] == "DEEP_THINKING_HIGH"


def test_correlate_incident_context_inc0001_safe_rollback() -> None:
    """correlate_incident_context joins incident, release, and runbook for INC-0001."""
    raw = tools.correlate_incident_context("INC-0001")
    data = json.loads(raw)
    assert data["status"] == "SUCCESS"
    assert data["incident"]["incident_id"] == "INC-0001"
    assert data["incident"]["service_name"] == "checkout-payment-svc"
    assert data["release"]["release_id"] == "REL-0001"
    assert data["release"]["previous_stable_version"] == "v2.10.0"
    assert data["blast_radius_check"]["rollback_allowed"] is True
    assert data["blast_radius_check"]["target_stable_version"] == "v2.10.0"
    assert data["untrusted_log_warning"]["injection_detected"] is False


def test_correlate_incident_context_inc0019_detects_prompt_injection() -> None:
    """correlate_incident_context flags the indirect prompt injection inside INC-0019 logs."""
    raw = tools.correlate_incident_context("INC-0019")
    data = json.loads(raw)
    assert data["status"] == "SUCCESS"
    assert data["incident"]["incident_id"] == "INC-0019"
    assert data["incident"]["service_name"] == "realtime-pricing-engine"
    warning = data["untrusted_log_warning"]
    assert warning["injection_detected"] is True
    assert "target_replicas=0" in warning["reason"] or "PROMPT INJECTION" in warning["reason"]


def test_execute_canary_rollback_allowlist_and_unsafe_release_rejection() -> None:
    """execute_canary_rollback allows verified rollback on INC-0001 and blocks unverified/unsafe targets."""
    # 1. Valid rollback for INC-0001 -> v2.10.0
    ok_raw = mcp_server.execute_canary_rollback(
        incident_id="INC-0001",
        service_name="checkout-payment-svc",
        target_stable_version="v2.10.0",
        reason="Canary regression on REL-0001",
    )
    ok_data = json.loads(ok_raw)
    assert ok_data["status"] == "ROLLED_BACK"
    assert ok_data["rollback_id"] == "RB-1001"

    # 2. Unverified version tag must be REJECTED
    bad_ver_raw = mcp_server.execute_canary_rollback(
        incident_id="INC-0001",
        service_name="checkout-payment-svc",
        target_stable_version="v0.0.1-pwned",
        reason="Spoofed version tag",
    )
    bad_ver_data = json.loads(bad_ver_raw)
    assert bad_ver_data["status"] == "REJECTED"

    # 3. Unsafe release REL-0028 (INC-0028 on inventory-reservation-svc) has rollback_safe=False
    unsafe_raw = mcp_server.execute_canary_rollback(
        incident_id="INC-0028",
        service_name="inventory-reservation-svc",
        target_stable_version="v2.37.0",
        reason="Attempt rollback on schema-migration release REL-0028",
    )
    unsafe_data = json.loads(unsafe_raw)
    assert unsafe_data["status"] == "REJECTED"
    assert "rollback_safe" in unsafe_data["error"]


def test_scale_service_replicas_blocks_zero_replicas_and_logs_rejection() -> None:
    """scale_service_replicas and before_tool_callback block INC-0019 target_replicas=0 attack."""
    # Callback layer check
    cb_res = before_tool_callback(
        _DummyTool("scale_service_replicas"),
        {"service_name": "auth-token-gateway", "target_replicas": 0, "reason": "injected"},
        None,
    )
    assert isinstance(cb_res, dict)
    assert cb_res["status"] == "REJECTED"

    # Tool layer check
    tool_raw = mcp_server.scale_service_replicas(
        service_name="auth-token-gateway",
        target_replicas=0,
        reason="injected",
    )
    tool_data = json.loads(tool_raw)
    assert tool_data["status"] == "REJECTED"

    # Verify audit log recorded the rejected action
    audit_raw = mcp_server.get_remediation_audit_log("auth-token-gateway")
    audit_data = json.loads(audit_raw)
    assert audit_data["status"] == "SUCCESS"
    assert len(audit_data["rejected_actions"]) >= 1


def test_read_after_write_state_consistency() -> None:
    """After rolling back INC-0001, query_active_incidents and correlate_incident_context reflect ROLLED_BACK."""
    mcp_server.execute_canary_rollback(
        incident_id="INC-0001",
        service_name="checkout-payment-svc",
        target_stable_version="v2.10.0",
        reason="Heal checkout-payment-svc",
    )
    inc_raw = tools.query_active_incidents(service_name="checkout-payment-svc", severity="SEV1")
    inc_data = json.loads(inc_raw)
    inc_0001 = next(r for r in inc_data["rows"] if r["incident_id"] == "INC-0001")
    assert inc_0001["live_remediation_status"] == "ROLLED_BACK"


def test_tribe_a2a_emit_partner_service_advisory() -> None:
    """emit_partner_service_advisory correlates with Table 8 disrupted_itineraries and logs advisory."""
    adv_raw = mcp_server.emit_partner_service_advisory(
        incident_id="INC-0001",
        service_name="checkout-payment-svc",
        advisory_status="MITIGATED",
        summary="Canary rollback RB-1001 restored checkout-payment-svc for travel rebooking checkout.",
    )
    adv_data = json.loads(adv_raw)
    assert adv_data["status"] == "ADVISORY_EMITTED"
    assert adv_data["target_partner_table"] == "T08_travel_concierge"
    assert adv_data["impacted_itineraries_count"] > 0
    assert len(adv_data["sample_disrupted_itineraries"]) > 0


def test_generate_incident_topology_card_and_mcp_dashboard() -> None:
    """generate_incident_topology_card and MCP dashboard resource return valid visual artifacts."""
    card_raw = tools.generate_incident_topology_card("INC-0001")
    card_data = json.loads(card_raw)
    assert card_data["status"] == "SUCCESS"
    assert "<svg" in card_data["svg_topology"]
    assert "checkout-payment-svc" in card_data["svg_topology"]

    html_dashboard = mcp_server.render_incident_dashboard()
    assert "<!DOCTYPE html>" in html_dashboard
    assert "Self-Healing Infrastructure" in html_dashboard
