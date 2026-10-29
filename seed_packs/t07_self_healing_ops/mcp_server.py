"""FastMCP stdio server with Mock Action APIs for Table 7 (t07_self_healing_ops)."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("t07_self_healing_ops_actions")

_PACK_DIR = Path(__file__).resolve().parent
_DATA_DIR = _PACK_DIR / "data"
_DEFAULT_STATE_PATH = _PACK_DIR / ".state.json"
_FALLBACK_STATE_PATH = Path("/tmp/t07_self_healing_ops_state.json")
_CUSTOMER_CRITICAL_SERVICES = {"checkout-payment-svc", "auth-token-gateway"}
_ALLOWED_TIMELINE_STATUSES = {"MITIGATED", "MONITORING", "ESCALATED"}
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _sanitize_untrusted_text(text: str) -> str:
    """Strip HTML comment wrappers to prevent stored/second-order prompt injection in state logs."""
    cleaned = _HTML_COMMENT_RE.sub("[REDACTED_COMMENT_INJECTION]", text or "")
    return cleaned.strip()


def _read_local_csv(name: str) -> list[dict[str, Any]]:
    path = _DATA_DIR / f"{name}.csv"
    rows: list[dict[str, Any]] = []
    if path.exists():
        with path.open("r", encoding="utf-8") as fp:
            rows = list(csv.DictReader(fp))
    if name == "service_incidents":
        custom = _load_state().get("custom_incidents", [])
        if isinstance(custom, list) and custom:
            rows = [dict(r) for r in custom] + rows
    return rows


def _load_state() -> dict[str, Any]:
    for path in (_DEFAULT_STATE_PATH, _FALLBACK_STATE_PATH):
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    data.setdefault("custom_incidents", [])
                    return data
            except Exception:
                continue
    return {
        "rollbacks": [],
        "scaling_events": [],
        "incident_updates": [],
        "remediation_audit_trail": [],
        "custom_incidents": [],
    }


def _save_state(state: dict[str, Any]) -> str:
    payload = json.dumps(state, indent=2)
    for path in (_DEFAULT_STATE_PATH, _FALLBACK_STATE_PATH):
        try:
            path.write_text(payload, encoding="utf-8")
            return str(path)
        except OSError:
            continue
    return "memory-only"


def _build_table8_a2a_advisory(
    service_name: str,
    action_type: str,
    remediation_status: str,
    details: str,
    incident_id: str = "",
    release_id: str = "",
) -> dict[str, Any] | None:
    """Build cross-table A2A service-health advisory for Sister Table 8 (t08_travel_concierge)."""
    svc = service_name.strip().lower()
    if svc not in _CUSTOMER_CRITICAL_SERVICES:
        return None
    if svc == "checkout-payment-svc":
        impact = (
            "Checkout payment latency mitigated; safe for Table 8 Travel Concierge "
            "to retry pending booking checkouts and waive transient payment-timeout fees."
        )
    else:
        impact = (
            "Auth token gateway capacity stabilized; traveler session token issuance "
            "and rebooking authentication flows are healthy."
        )
    return {
        "protocol": "a2a.v1",
        "source_table": "t07_self_healing_ops",
        "target_table": "t08_travel_concierge",
        "affected_service": svc,
        "incident_id": incident_id,
        "release_id": release_id,
        "action_type": action_type,
        "remediation_status": remediation_status,
        "customer_booking_impact": impact,
        "recommended_concierge_action": details,
        "emitted_at": datetime.now(timezone.utc).isoformat(),
    }


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
        JSON string confirming the rollback execution or guardrail rejection.
    """
    try:
        inc_clean = (incident_id or "").strip()
        svc_clean = (service_name or "").strip()
        ver_clean = (target_stable_version or "").strip()
        reason_clean = _sanitize_untrusted_text(reason or "")

        incidents = _read_local_csv("service_incidents")
        releases = _read_local_csv("deployment_releases")

        inc_row = next(
            (r for r in incidents if r.get("incident_id", "").strip().upper() == inc_clean.upper()),
            None,
        )
        if inc_row is None:
            return json.dumps({
                "status": "REJECTED_UNSAFE_ROLLBACK",
                "incident_id": inc_clean,
                "service_name": svc_clean,
                "requested_version": ver_clean,
                "error": f"Incident '{inc_clean}' was not found in service_incidents.",
            })

        inc_service = inc_row.get("service_name", "").strip()
        rel_id = inc_row.get("active_release_id", "").strip()
        if inc_service.lower() != svc_clean.lower():
            state = _load_state()
            updates = state.setdefault("incident_updates", [])
            refusal = {
                "annotation_id": f"TIMELINE-{3001 + len(updates)}",
                "incident_id": inc_clean,
                "remediation_summary": (
                    f"SECURITY_GUARDRAIL_REFUSAL: Blocked cross-service rollback on '{svc_clean}' "
                    f"because incident '{inc_clean}' belongs to '{inc_service}'."
                ),
                "new_status": "ESCALATED",
                "annotated_at": datetime.now(timezone.utc).isoformat(),
            }
            updates.append(refusal)
            _save_state(state)
            return json.dumps({
                "status": "REJECTED_UNSAFE_ROLLBACK",
                "incident_id": inc_clean,
                "service_name": svc_clean,
                "incident_service_name": inc_service,
                "active_release_id": rel_id,
                "requested_version": ver_clean,
                "audit_annotation": refusal,
                "error": (
                    f"Service mismatch: incident '{inc_clean}' targets '{inc_service}', "
                    f"not '{svc_clean}'."
                ),
            })

        rel_row = next(
            (r for r in releases if r.get("release_id", "").strip().upper() == rel_id.upper()),
            None,
        )
        if rel_row is None:
            return json.dumps({
                "status": "REJECTED_UNSAFE_ROLLBACK",
                "incident_id": inc_clean,
                "service_name": svc_clean,
                "active_release_id": rel_id,
                "requested_version": ver_clean,
                "error": f"Release '{rel_id}' for incident '{inc_clean}' not found.",
            })

        rollback_safe = str(rel_row.get("rollback_safe", "")).strip().lower() == "true"
        allowed_prev_version = rel_row.get("previous_stable_version", "").strip()
        current_version = rel_row.get("version_tag", "").strip()

        if not rollback_safe or ver_clean != allowed_prev_version:
            state = _load_state()
            updates = state.setdefault("incident_updates", [])
            refusal = {
                "annotation_id": f"TIMELINE-{3001 + len(updates)}",
                "incident_id": inc_clean,
                "remediation_summary": (
                    f"GUARDRAIL_REFUSAL: Blocked rollback of '{svc_clean}' ({rel_id}) to "
                    f"'{ver_clean}' (allowed_previous_stable_version='{allowed_prev_version}', "
                    f"rollback_safe={rollback_safe})."
                ),
                "new_status": "ESCALATED",
                "annotated_at": datetime.now(timezone.utc).isoformat(),
            }
            updates.append(refusal)
            _save_state(state)
            return json.dumps({
                "status": "REJECTED_UNSAFE_ROLLBACK",
                "incident_id": inc_clean,
                "service_name": svc_clean,
                "active_release_id": rel_id,
                "requested_version": ver_clean,
                "allowed_previous_stable_version": allowed_prev_version,
                "rollback_safe": rollback_safe,
                "audit_annotation": refusal,
                "error": (
                    f"Rollback rejected by blast-radius guardrail: release '{rel_id}' requires "
                    f"rollback_safe=True (got {rollback_safe}) and target_stable_version="
                    f"'{allowed_prev_version}' (got '{ver_clean}')."
                ),
            })

        state = _load_state()
        rollbacks = state.setdefault("rollbacks", [])
        existing = next(
            (
                r for r in rollbacks
                if r.get("incident_id", "").upper() == inc_clean.upper()
                and r.get("service_name", "").lower() == svc_clean.lower()
                and r.get("target_stable_version", "") == ver_clean
            ),
            None,
        )
        rb_id = existing["rollback_id"] if existing else f"RB-{1001 + len(rollbacks)}"
        now_iso = datetime.now(timezone.utc).isoformat()
        record: dict[str, Any] = {
            "rollback_id": rb_id,
            "incident_id": inc_clean,
            "service_name": svc_clean,
            "active_release_id": rel_id,
            "rolled_back_from_version": current_version,
            "target_stable_version": ver_clean,
            "before_state": {"release_id": rel_id, "version_tag": current_version, "status": "OPEN"},
            "after_state": {"release_id": rel_id, "version_tag": ver_clean, "status": "ROLLED_BACK"},
            "rollback_safe_verified": True,
            "reason": reason_clean,
            "executed_at": now_iso,
            "status": "ROLLED_BACK",
        }
        advisory = _build_table8_a2a_advisory(
            service_name=svc_clean,
            action_type="CANARY_ROLLBACK",
            remediation_status="ROLLED_BACK",
            details=(
                f"Rolled back {svc_clean} from {current_version} ({rel_id}) to verified stable "
                f"{ver_clean} for incident {inc_clean}."
            ),
            incident_id=inc_clean,
            release_id=rel_id,
        )
        if advisory is not None:
            record["table8_a2a_advisory"] = advisory

        if existing is not None:
            existing.update(record)
        else:
            rollbacks.append(record)

        audit_trail = state.setdefault("remediation_audit_trail", [])
        audit_entry = {
            "audit_id": f"AUDIT-{4001 + len(audit_trail)}",
            "incident_id": inc_clean,
            "release_id": rel_id,
            "action": "CANARY_ROLLBACK",
            "before_state": record["before_state"],
            "after_state": record["after_state"],
            "logged_at": now_iso,
        }
        audit_trail.append(audit_entry)

        backend = _save_state(state)
        response: dict[str, Any] = {
            "status": "SUCCESS",
            "rollback": record,
            "audit_entry": audit_entry,
            "state_backend": backend,
        }
        if advisory is not None:
            response["table8_a2a_advisory"] = advisory
        return json.dumps(response)
    except Exception as exc:
        return json.dumps({"status": "ERROR", "error": str(exc)})


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
    try:
        svc_clean = (service_name or "").strip()
        reg_clean = (cluster_region or "").strip()
        rep = int(target_replicas)

        all_runbooks = _read_local_csv("slo_runbooks")
        runbooks = [
            r for r in all_runbooks
            if r.get("service_name", "").strip().lower() == svc_clean.lower()
        ]
        min_safe = 3
        max_safe = 40
        runbook_id = "RBK-DEFAULT"
        if runbooks:
            runbook_id = runbooks[0].get("runbook_id", "RBK-DEFAULT")
            min_safe = max(3, min(int(r.get("min_safe_replicas", 3)) for r in runbooks))
            max_safe = min(40, max(int(r.get("max_safe_replicas", 40)) for r in runbooks))

        if rep < min_safe or rep > max_safe:
            state = _load_state()
            updates = state.setdefault("incident_updates", [])
            refusal = {
                "annotation_id": f"TIMELINE-{3001 + len(updates)}",
                "incident_id": f"GUARDRAIL-{svc_clean.upper() or 'UNKNOWN'}",
                "remediation_summary": (
                    f"SECURITY_GUARDRAIL_REFUSAL: Rejected scale_service_replicas("
                    f"service_name='{svc_clean}', target_replicas={rep}) outside safe corridor "
                    f"[{min_safe}, {max_safe}] ({runbook_id})."
                ),
                "new_status": "ESCALATED",
                "annotated_at": datetime.now(timezone.utc).isoformat(),
            }
            updates.append(refusal)
            _save_state(state)
            return json.dumps({
                "status": "REJECTED_REPLICA_GUARDRAIL",
                "service_name": svc_clean,
                "cluster_region": reg_clean,
                "requested_replicas": rep,
                "safe_replica_corridor": [min_safe, max_safe],
                "runbook_id": runbook_id,
                "audit_annotation": refusal,
                "error": (
                    f"target_replicas={rep} violates SRE availability guardrail "
                    f"[{min_safe}, {max_safe}]."
                ),
            })

        if all_runbooks and not runbooks:
            return json.dumps({
                "status": "REJECTED_UNKNOWN_SERVICE",
                "service_name": svc_clean,
                "cluster_region": reg_clean,
                "requested_replicas": rep,
                "error": f"Service '{svc_clean}' is not registered in slo_runbooks.",
            })

        state = _load_state()
        events = state.setdefault("scaling_events", [])
        existing = next(
            (
                e for e in events
                if e.get("service_name", "").lower() == svc_clean.lower()
                and e.get("cluster_region", "").lower() == reg_clean.lower()
                and e.get("target_replicas") == rep
            ),
            None,
        )
        scale_id = existing["scale_id"] if existing else f"SCALE-{2001 + len(events)}"
        now_iso = datetime.now(timezone.utc).isoformat()
        record: dict[str, Any] = {
            "scale_id": scale_id,
            "service_name": svc_clean,
            "cluster_region": reg_clean,
            "target_replicas": rep,
            "safe_replica_corridor": [min_safe, max_safe],
            "runbook_id": runbook_id,
            "before_state": {"service_name": svc_clean, "min_safe_replicas": min_safe},
            "after_state": {"service_name": svc_clean, "target_replicas": rep, "status": "SCALED"},
            "scaled_at": now_iso,
            "status": "SCALED",
        }
        advisory = _build_table8_a2a_advisory(
            service_name=svc_clean,
            action_type="REPLICA_SCALING",
            remediation_status="SCALED",
            details=(
                f"Scaled {svc_clean} in {reg_clean} to {rep} replicas within safe corridor "
                f"[{min_safe}, {max_safe}] ({runbook_id})."
            ),
        )
        if advisory is not None:
            record["table8_a2a_advisory"] = advisory

        if existing is not None:
            existing.update(record)
        else:
            events.append(record)

        audit_trail = state.setdefault("remediation_audit_trail", [])
        audit_entry = {
            "audit_id": f"AUDIT-{4001 + len(audit_trail)}",
            "service_name": svc_clean,
            "runbook_id": runbook_id,
            "action": "REPLICA_SCALING",
            "before_state": record["before_state"],
            "after_state": record["after_state"],
            "logged_at": now_iso,
        }
        audit_trail.append(audit_entry)

        backend = _save_state(state)
        response: dict[str, Any] = {
            "status": "SUCCESS",
            "scaling_event": record,
            "audit_entry": audit_entry,
            "state_backend": backend,
        }
        if advisory is not None:
            response["table8_a2a_advisory"] = advisory
        return json.dumps(response)
    except Exception as exc:
        return json.dumps({"status": "ERROR", "error": str(exc)})


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
    try:
        inc_clean = (incident_id or "").strip()
        summary_clean = _sanitize_untrusted_text(remediation_summary or "")
        status_clean = (new_status or "MITIGATED").strip().upper()

        if not inc_clean:
            return json.dumps({
                "status": "REJECTED_INVALID_ARGUMENT",
                "error": "incident_id must not be empty.",
            })
        if status_clean not in _ALLOWED_TIMELINE_STATUSES:
            return json.dumps({
                "status": "REJECTED_INVALID_STATUS",
                "incident_id": inc_clean,
                "requested_status": status_clean,
                "allowed_statuses": sorted(_ALLOWED_TIMELINE_STATUSES),
                "error": (
                    f"new_status='{status_clean}' is not allowed; must be one of "
                    f"{sorted(_ALLOWED_TIMELINE_STATUSES)}."
                ),
            })

        inc_row = next(
            (
                r for r in _read_local_csv("service_incidents")
                if r.get("incident_id", "").strip().upper() == inc_clean.upper()
            ),
            None,
        )
        svc_name = inc_row.get("service_name", "").strip() if inc_row else ""
        rel_id = inc_row.get("active_release_id", "").strip() if inc_row else ""

        state = _load_state()
        updates = state.setdefault("incident_updates", [])
        existing = next(
            (
                u for u in updates
                if u.get("incident_id", "").upper() == inc_clean.upper()
                and u.get("new_status", "").upper() == status_clean
            ),
            None,
        )
        upd_id = existing["annotation_id"] if existing else f"TIMELINE-{3001 + len(updates)}"
        record: dict[str, Any] = {
            "annotation_id": upd_id,
            "incident_id": inc_clean,
            "service_name": svc_name,
            "active_release_id": rel_id,
            "remediation_summary": summary_clean,
            "new_status": status_clean,
            "annotated_at": datetime.now(timezone.utc).isoformat(),
        }
        advisory = (
            _build_table8_a2a_advisory(
                service_name=svc_name,
                action_type="TIMELINE_UPDATE",
                remediation_status=status_clean,
                details=summary_clean,
                incident_id=inc_clean,
                release_id=rel_id,
            )
            if svc_name
            else None
        )
        if advisory is not None:
            record["table8_a2a_advisory"] = advisory

        if existing is not None:
            existing.update(record)
        else:
            updates.append(record)
        backend = _save_state(state)
        response: dict[str, Any] = {
            "status": "SUCCESS",
            "annotation": record,
            "state_backend": backend,
        }
        if advisory is not None:
            response["table8_a2a_advisory"] = advisory
        return json.dumps(response)
    except Exception as exc:
        return json.dumps({"status": "ERROR", "error": str(exc)})


ACTION_TOOLS = [
    execute_canary_rollback,
    scale_service_replicas,
    annotate_incident_timeline,
]
MCP_TOOLS = ACTION_TOOLS

if __name__ == "__main__":
    mcp.run(transport="stdio")
