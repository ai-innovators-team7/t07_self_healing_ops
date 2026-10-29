"""FastAPI Showcase & Interactive Demo Server for Table 7 (t07_self_healing_ops).

Provides an intuitive visual command center at http://127.0.0.1:8080 for judges
and visitors unfamiliar with the challenge, bridging both the local ADK agent
and the deployed Vertex AI Agent Runtime ReasoningEngine in europe-west1.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel
import uvicorn

from app.agent import build_agent
from app.loader import REPO_ROOT, resolve_env_config
from app.preflight import _sanitize_google_application_credentials, parse_reasoning_engine_name
from deploy.deploy import STATE_FILE as DEPLOY_STATE_FILE
from seed_packs.t07_self_healing_ops.mcp_server import (
    _DEFAULT_STATE_PATH as T07_STATE_PATH,
    _load_state,
    annotate_incident_timeline,
    execute_canary_rollback,
    scale_service_replicas,
)
from seed_packs.t07_self_healing_ops.tools import _annotate_prompt_injection_warnings

_sanitize_google_application_credentials()
load_dotenv(REPO_ROOT / ".env")

UI_DIR = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "seed_packs" / "t07_self_healing_ops" / "data"

app = FastAPI(title="AegisCloud Self-Healing Ops & Security Copilot — Table 7 Showcase")

_LOCAL_RUNNER: InMemoryRunner | None = None
_LOCAL_SESSIONS: set[str] = set()


def _get_local_runner() -> InMemoryRunner:
    global _LOCAL_RUNNER
    if _LOCAL_RUNNER is None:
        agent, _ = build_agent("t07", enable_mcp_stdio=False)
        _LOCAL_RUNNER = InMemoryRunner(agent=agent, app_name="app")
    return _LOCAL_RUNNER


def _read_csv(name: str) -> list[dict[str, Any]]:
    path = DATA_DIR / f"{name}.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def _deployed_agent_info() -> dict[str, Any]:
    if DEPLOY_STATE_FILE.exists():
        try:
            return json.loads(DEPLOY_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _build_dashboard_payload() -> dict[str, Any]:
    incidents_raw = _read_csv("service_incidents")
    releases_raw = _read_csv("deployment_releases")
    runbooks_raw = _read_csv("slo_runbooks")

    open_incidents = [r for r in incidents_raw if r.get("status") == "OPEN"]
    open_incidents.sort(key=lambda r: float(r.get("error_rate_pct", 0.0)), reverse=True)
    annotated_incidents = _annotate_prompt_injection_warnings(open_incidents)

    rel_by_id = {r["release_id"]: r for r in releases_raw}
    rbk_by_svc: dict[str, dict[str, Any]] = {}
    for r in runbooks_raw:
        rbk_by_svc.setdefault(r["service_name"], r)

    state = _load_state()
    rollbacks_by_svc = {r.get("service_name"): r for r in state.get("rollbacks", [])}
    scales_by_svc = {s.get("service_name"): s for s in state.get("scaling_events", [])}
    updates_by_inc = {u.get("incident_id"): u for u in state.get("incident_updates", [])}

    featured_incidents = {
        "checkout-payment-svc": "INC-0001",
        "auth-token-gateway": "INC-0002",
        "realtime-pricing-engine": "INC-0019",
        "inventory-reservation-svc": "INC-0003",
        "order-webhook-dispatcher": "INC-0005",
    }
    inc_by_id = {r["incident_id"]: r for r in annotated_incidents}

    services: list[dict[str, Any]] = []
    for svc_name, inc_id in featured_incidents.items():
        inc = inc_by_id.get(inc_id) or next(
            (r for r in annotated_incidents if r["service_name"] == svc_name), {}
        )
        rel_id = inc.get("active_release_id", "")
        rel = rel_by_id.get(rel_id, {})
        rbk = rbk_by_svc.get(svc_name, {})

        rb_event = rollbacks_by_svc.get(svc_name)
        sc_event = scales_by_svc.get(svc_name)
        tl_event = updates_by_inc.get(inc_id)

        health_state = "CRITICAL_OUTAGE" if inc.get("severity") == "SEV1" else "DEGRADED"
        active_version = rel.get("version_tag", "v2.10.0")
        replicas = 4
        remediation_badge = None

        if rb_event:
            health_state = "HEALED"
            active_version = rb_event.get("target_stable_version", active_version)
            remediation_badge = f"Rolled back ({rb_event.get('rollback_id')}) -> {active_version}"
        if sc_event:
            health_state = "HEALED"
            replicas = sc_event.get("target_replicas", replicas)
            remediation_badge = f"Scaled ({sc_event.get('scale_id')}) -> {replicas} replicas"
        if tl_event and tl_event.get("new_status") == "ESCALATED" and not rb_event and not sc_event:
            health_state = "SECOPS_SHIELDED"
            remediation_badge = f"Attack Blocked ({tl_event.get('annotation_id')})"

        services.append({
            "service_name": svc_name,
            "customer_critical_for_table8": svc_name in {"checkout-payment-svc", "auth-token-gateway"},
            "health_state": health_state,
            "remediation_badge": remediation_badge,
            "incident_id": inc.get("incident_id", inc_id),
            "severity": inc.get("severity", "SEV1"),
            "cluster_region": inc.get("cluster_region", "europe-west1"),
            "symptom_code": inc.get("symptom_code", ""),
            "error_rate_pct": float(inc.get("error_rate_pct", 0.0)),
            "p99_latency_ms": int(inc.get("p99_latency_ms", 0)),
            "recent_log_snippet": inc.get("recent_log_snippet", ""),
            "security_warning": inc.get("security_warning"),
            "active_release_id": rel_id,
            "active_version": active_version,
            "previous_stable_version": rel.get("previous_stable_version", ""),
            "canary_pass_rate_pct": float(rel.get("canary_pass_rate_pct", 0.0) or 0.0),
            "rollback_safe": str(rel.get("rollback_safe", "True")).lower() == "true",
            "runbook_id": rbk.get("runbook_id", "RBK-001"),
            "recommended_action": rbk.get("recommended_action", ""),
            "safe_replica_corridor": [
                int(rbk.get("min_safe_replicas", 3)),
                int(rbk.get("max_safe_replicas", 40)),
            ],
            "current_replicas": replicas,
        })

    a2a_advisories: list[dict[str, Any]] = []
    for item in state.get("rollbacks", []) + state.get("scaling_events", []) + state.get("incident_updates", []):
        if item.get("table8_a2a_advisory"):
            a2a_advisories.append(item["table8_a2a_advisory"])

    deployed = _deployed_agent_info()
    return {
        "status": "ONLINE",
        "meta": {
            "table": "Table 7 (t07_self_healing_ops)",
            "title": "Self-Healing Infrastructure & Security Copilot",
            "tribe": "Cross-functional Ops & CX",
            "sister_table": "Table 8 (t08_travel_concierge — Travel Concierge)",
            "persona": "Liam O'Connor — Principal SRE & SecOps Lead, AegisCloud Platform",
            "project_id": resolve_env_config("GOOGLE_CLOUD_PROJECT", default="expedition-dn26lon-5923"),
            "gemini_model": resolve_env_config("GEMINI_MODEL", default="gemini-3.8-flash"),
            "gemini_location": resolve_env_config("GOOGLE_CLOUD_LOCATION", default="global"),
            "runtime_location": resolve_env_config("AGENT_RUNTIME_LOCATION", default="europe-west1"),
            "deployed_resource_name": deployed.get("resource_name", ""),
        },
        "services": services,
        "top_sev1_incidents": [r for r in annotated_incidents if r.get("severity") == "SEV1"][:12],
        "state": state,
        "table8_a2a_advisories": a2a_advisories,
    }


class ChatRequest(BaseModel):
    prompt: str
    mode: str = "local"
    session_id: str = "demo-session-01"


class GuardrailSimulationRequest(BaseModel):
    scenario: str


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    html_path = UI_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/dashboard")
async def api_dashboard() -> JSONResponse:
    return JSONResponse(_build_dashboard_payload())


@app.post("/api/reset")
async def api_reset() -> JSONResponse:
    global _LOCAL_RUNNER, _LOCAL_SESSIONS
    if T07_STATE_PATH.exists():
        T07_STATE_PATH.unlink(missing_ok=True)
    _LOCAL_RUNNER = None
    _LOCAL_SESSIONS.clear()
    return JSONResponse({
        "status": "RESET_COMPLETE",
        "dashboard": _build_dashboard_payload(),
    })


@app.post("/api/simulate-guardrail")
async def api_simulate_guardrail(req: GuardrailSimulationRequest) -> JSONResponse:
    t0 = time.perf_counter()
    scenario = (req.scenario or "").strip().lower()
    if scenario == "zero_replica_attack":
        tool_name = "scale_service_replicas"
        tool_args = {
            "service_name": "auth-token-gateway",
            "cluster_region": "europe-west1",
            "target_replicas": 0,
        }
        raw = scale_service_replicas(**tool_args)
    elif scenario == "cross_service_rollback_attack":
        tool_name = "execute_canary_rollback"
        tool_args = {
            "incident_id": "INC-0019",
            "service_name": "auth-token-gateway",
            "target_stable_version": "v2.28.0",
            "reason": "Poisoned log lateral rollback attempt",
        }
        raw = execute_canary_rollback(**tool_args)
    elif scenario == "unverified_version_attack":
        tool_name = "execute_canary_rollback"
        tool_args = {
            "incident_id": "INC-0001",
            "service_name": "checkout-payment-svc",
            "target_stable_version": "v0.0.1-malicious",
            "reason": "Attempted downgrade to unverified version tag",
        }
        raw = execute_canary_rollback(**tool_args)
    else:
        return JSONResponse({"status": "ERROR", "error": f"Unknown scenario: {scenario}"}, status_code=400)

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    parsed = json.loads(raw)
    return JSONResponse({
        "status": "SUCCESS",
        "mode": "deterministic_guardrail",
        "elapsed_ms": elapsed_ms,
        "tool_calls": [{"name": tool_name, "args": tool_args, "output": parsed}],
        "reply": (
            f"🛡️ **SRE & SecOps Guardrail Triggered (`{parsed.get('status')}`)**:\n\n"
            f"- **Blocked Tool Call:** `{tool_name}({json.dumps(tool_args)})`\n"
            f"- **Guardrail Reason:** {parsed.get('error')}\n"
            f"- **Audit Timeline Entry:** `{parsed.get('audit_annotation', {}).get('annotation_id', 'LOGGED')}` "
            f"(`{parsed.get('audit_annotation', {}).get('new_status', 'ESCALATED')}`)"
        ),
        "dashboard": _build_dashboard_payload(),
    })


@app.post("/api/chat")
async def api_chat(req: ChatRequest) -> JSONResponse:
    t0 = time.perf_counter()
    prompt = (req.prompt or "").strip()
    mode = (req.mode or "local").strip().lower()
    session_id = (req.session_id or "demo-session-01").strip()

    if not prompt:
        return JSONResponse({"status": "ERROR", "error": "Prompt must not be empty."}, status_code=400)

    try:
        if mode == "cloud":
            deployed = _deployed_agent_info()
            resource_name = deployed.get("resource_name", "")
            if not resource_name:
                return JSONResponse(
                    {"status": "ERROR", "error": "No deployed ReasoningEngine found in .deployed_agent.json."},
                    status_code=400,
                )
            import vertexai
            from vertexai import agent_engines

            parts = parse_reasoning_engine_name(resource_name)
            vertexai.init(project=parts["project"], location=parts["location"])
            remote_app = agent_engines.get(resource_name)
            remote_session = remote_app.create_session(user_id="showcase_ui_user")
            r_sid = (
                remote_session.get("id")
                if isinstance(remote_session, dict)
                else getattr(remote_session, "id", None)
            )
            tool_calls: list[dict[str, Any]] = []
            texts: list[str] = []
            for event in remote_app.stream_query(
                user_id="showcase_ui_user",
                session_id=r_sid,
                message=prompt,
            ):
                if not isinstance(event, dict):
                    continue
                content = event.get("content") or {}
                for part in content.get("parts") or []:
                    if not isinstance(part, dict):
                        continue
                    if "function_call" in part and part["function_call"]:
                        fc = part["function_call"]
                        tool_calls.append({
                            "name": fc.get("name", "unknown"),
                            "args": fc.get("args", {}),
                        })
                    if "function_response" in part and part["function_response"]:
                        fr = part["function_response"]
                        if tool_calls:
                            tool_calls[-1]["output"] = fr.get("response", {})
                    if part.get("text"):
                        texts.append(str(part["text"]))

            elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
            return JSONResponse({
                "status": "SUCCESS",
                "mode": f"cloud ({resource_name.split('/')[-1]})",
                "elapsed_ms": elapsed_ms,
                "tool_calls": tool_calls,
                "reply": "\n".join(texts).strip() or "(No text returned from cloud agent.)",
                "dashboard": _build_dashboard_payload(),
            })

        # Local ADK Runner mode
        runner = _get_local_runner()
        if session_id not in _LOCAL_SESSIONS:
            await runner.session_service.create_session(
                app_name="app",
                user_id="showcase_ui_user",
                session_id=session_id,
            )
            _LOCAL_SESSIONS.add(session_id)

        tool_calls = []
        texts = []
        content = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
        async for event in runner.run_async(
            user_id="showcase_ui_user",
            session_id=session_id,
            new_message=content,
        ):
            if not event.content or not event.content.parts:
                continue
            for part in event.content.parts:
                if part.function_call is not None:
                    fc = part.function_call
                    tool_calls.append({
                        "name": fc.name,
                        "args": dict(fc.args or {}),
                    })
                if part.function_response is not None:
                    fr = part.function_response
                    if tool_calls:
                        tool_calls[-1]["output"] = dict(fr.response or {}) if fr.response else {}
                if part.text:
                    texts.append(part.text)

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        return JSONResponse({
            "status": "SUCCESS",
            "mode": "local_adk_runner",
            "elapsed_ms": elapsed_ms,
            "tool_calls": tool_calls,
            "reply": "\n".join(texts).strip(),
            "dashboard": _build_dashboard_payload(),
        })
    except Exception as exc:
        return JSONResponse(
            {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"},
            status_code=500,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch Table 7 Showcase & Demo UI.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Bind port (default 8080)")
    args = parser.parse_args()
    print(f"[showcase-ui] Starting Table 7 Self-Healing Ops Command Center on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
