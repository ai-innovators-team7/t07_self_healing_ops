"""FastMCP stdio server with Mock Action APIs for Table 7 (t07_self_healing_ops)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("t07_self_healing_ops_actions")

_PACK_DIR = Path(__file__).resolve().parent
_DEFAULT_STATE_PATH = _PACK_DIR / ".state.json"
_FALLBACK_STATE_PATH = Path("/tmp/t07_self_healing_ops_state.json")


def _load_state() -> dict[str, Any]:
    for path in (_DEFAULT_STATE_PATH, _FALLBACK_STATE_PATH):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return {"rollbacks": [], "scaling_events": [], "incident_updates": []}


def _save_state(state: dict[str, Any]) -> str:
    payload = json.dumps(state, indent=2)
    for path in (_DEFAULT_STATE_PATH, _FALLBACK_STATE_PATH):
        try:
            path.write_text(payload, encoding="utf-8")
            return str(path)
        except OSError:
            continue
    return "memory-only"


@mcp.tool()
def execute_canary_rollback(
    incident_id: str,
    service_name: str,
    target_stable_version: str,
    reason: str,
) -> str:
    """Roll back a degraded microservice to its previous verified stable version.

    Args:
        incident_id: Active incident ID (e.g. 'INC-0001').
        service_name: Kubernetes service name (e.g. 'checkout-payment-svc').
        target_stable_version: Previous stable version tag (e.g. 'v2.10.0').
        reason: Root-cause summary justifying the rollback.

    Returns:
        JSON string confirming the rollback execution.
    """
    state = _load_state()
    rollbacks = state.setdefault("rollbacks", [])
    rb_id = f"RB-{1001 + len(rollbacks)}"
    record = {
        "rollback_id": rb_id,
        "incident_id": incident_id.strip(),
        "service_name": service_name.strip(),
        "target_stable_version": target_stable_version.strip(),
        "reason": reason.strip(),
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "status": "ROLLED_BACK",
    }
    rollbacks.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "rollback": record, "state_backend": backend})


@mcp.tool()
def scale_service_replicas(
    service_name: str,
    cluster_region: str,
    target_replicas: int,
) -> str:
    """Scale a service deployment replica count within the SRE safety corridor [3, 40].

    Args:
        service_name: Kubernetes service name (e.g. 'auth-token-gateway').
        cluster_region: Cluster region (e.g. 'europe-west1').
        target_replicas: Desired replica count (must be between 3 and 40; never 0).

    Returns:
        JSON string confirming replica scaling or safety rejection if outside [3, 40].
    """
    rep = int(target_replicas)
    if rep < 3 or rep > 40:
        return json.dumps({
            "status": "REJECTED_REPLICA_GUARDRAIL",
            "error": f"target_replicas={rep} violates SRE availability guardrail [3, 40].",
        })
    state = _load_state()
    events = state.setdefault("scaling_events", [])
    scale_id = f"SCALE-{2001 + len(events)}"
    record = {
        "scale_id": scale_id,
        "service_name": service_name.strip(),
        "cluster_region": cluster_region.strip(),
        "target_replicas": rep,
        "scaled_at": datetime.now(timezone.utc).isoformat(),
        "status": "SCALED",
    }
    events.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "scaling_event": record, "state_backend": backend})


@mcp.tool()
def annotate_incident_timeline(
    incident_id: str,
    remediation_summary: str,
    new_status: str = "MITIGATED",
) -> str:
    """Append a structured remediation entry to the incident timeline and update status.

    Args:
        incident_id: Incident ID (e.g. 'INC-0001').
        remediation_summary: Summary of diagnostic evidence and remediation actions taken.
        new_status: Updated incident status ('MITIGATED', 'MONITORING', or 'ESCALATED').

    Returns:
        JSON string with the recorded timeline annotation.
    """
    state = _load_state()
    updates = state.setdefault("incident_updates", [])
    upd_id = f"TIMELINE-{3001 + len(updates)}"
    record = {
        "annotation_id": upd_id,
        "incident_id": incident_id.strip(),
        "remediation_summary": remediation_summary.strip(),
        "new_status": new_status.strip().upper(),
        "annotated_at": datetime.now(timezone.utc).isoformat(),
    }
    updates.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "annotation": record, "state_backend": backend})


ACTION_TOOLS = [
    execute_canary_rollback,
    scale_service_replicas,
    annotate_incident_timeline,
]
MCP_TOOLS = ACTION_TOOLS

if __name__ == "__main__":
    mcp.run(transport="stdio")
