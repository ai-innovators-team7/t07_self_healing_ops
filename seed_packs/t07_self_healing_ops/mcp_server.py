"""FastMCP stdio server with Mock Action APIs and MCP App Dashboard for Table 7 (t07_self_healing_ops)."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("t07_self_healing_ops_actions")

_PACK_DIR = Path(__file__).resolve().parent
_DATA_DIR = _PACK_DIR / "data"
_T08_DATA_DIR = _PACK_DIR.parent / "t08_travel_concierge" / "data"
_DEFAULT_STATE_PATH = _PACK_DIR / ".state.json"
_FALLBACK_STATE_PATH = Path("/tmp/t07_self_healing_ops_state.json")


def _empty_state() -> dict[str, Any]:
    return {
        "rollbacks": [],
        "scaling_events": [],
        "incident_updates": [],
        "partner_advisories": [],
        "rejected_actions": [],
        "incident_status_overrides": {},
    }


def reset_state() -> None:
    """Remove persisted state files so tests and evaluations start from a clean slate."""
    for path in (_DEFAULT_STATE_PATH, _FALLBACK_STATE_PATH):
        try:
            if path.exists():
                path.unlink()
        except OSError:
            continue


def _load_state() -> dict[str, Any]:
    for path in (_DEFAULT_STATE_PATH, _FALLBACK_STATE_PATH):
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                base = _empty_state()
                base.update(loaded)
                return base
            except Exception:
                continue
    return _empty_state()


def _save_state(state: dict[str, Any]) -> str:
    payload = json.dumps(state, indent=2)
    saved_path = "memory-only"
    for path in (_DEFAULT_STATE_PATH, _FALLBACK_STATE_PATH):
        try:
            path.write_text(payload, encoding="utf-8")
            if saved_path == "memory-only":
                saved_path = str(path)
        except OSError:
            continue
    return saved_path


def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def _lookup_incident_and_release(
    incident_id: str,
    service_name: str,
) -> tuple[dict[str, str] | None, dict[str, str] | None]:
    incidents = _read_csv_rows(_DATA_DIR / "service_incidents.csv")
    releases = _read_csv_rows(_DATA_DIR / "deployment_releases.csv")
    inc_row = next(
        (r for r in incidents if r.get("incident_id", "").upper() == incident_id.strip().upper()),
        None,
    )
    rel_row = None
    if inc_row:
        active_rel = inc_row.get("active_release_id", "").strip().upper()
        rel_row = next(
            (r for r in releases if r.get("release_id", "").upper() == active_rel),
            None,
        )
    if rel_row is None and service_name:
        rel_row = next(
            (r for r in releases if r.get("service_name", "").lower() == service_name.strip().lower()),
            None,
        )
    return inc_row, rel_row


def _lookup_replica_corridor(service_name: str) -> tuple[int, int]:
    runbooks = _read_csv_rows(_DATA_DIR / "slo_runbooks.csv")
    for r in runbooks:
        if r.get("service_name", "").lower() == service_name.strip().lower():
            try:
                return int(r.get("min_safe_replicas", 3)), int(r.get("max_safe_replicas", 40))
            except ValueError:
                break
    return 3, 40


@mcp.tool()
def execute_canary_rollback(
    incident_id: str,
    service_name: str,
    target_stable_version: str,
    reason: str,
) -> str:
    """Roll back a degraded microservice to its previous verified stable version after blast-radius checks.

    Args:
        incident_id: Active incident ID (e.g. 'INC-0001').
        service_name: Kubernetes service name (e.g. 'checkout-payment-svc').
        target_stable_version: Previous stable version tag (e.g. 'v2.10.0').
        reason: Root-cause summary justifying the rollback.

    Returns:
        JSON string confirming the rollback execution or safety rejection if unsafe.
    """
    try:
        state = _load_state()
        inc_id = incident_id.strip().upper()
        svc = service_name.strip().lower()
        target_ver = target_stable_version.strip()
        inc_row, rel_row = _lookup_incident_and_release(inc_id, svc)

        if rel_row is not None:
            rollback_safe_str = str(rel_row.get("rollback_safe", "True")).strip().lower()
            is_rollback_safe = rollback_safe_str in {"true", "1", "yes"}
            expected_stable = str(rel_row.get("previous_stable_version", "")).strip()
            rel_id = str(rel_row.get("release_id", "UNKNOWN"))

            if not is_rollback_safe:
                rejection = {
                    "action": "execute_canary_rollback",
                    "incident_id": inc_id,
                    "service_name": svc,
                    "release_id": rel_id,
                    "target_stable_version": target_ver,
                    "reason": f"Release {rel_id} has rollback_safe=False (schema/config migration lock).",
                    "rejected_at": datetime.now(timezone.utc).isoformat(),
                }
                state.setdefault("rejected_actions", []).append(rejection)
                _save_state(state)
                return json.dumps({
                    "status": "REJECTED",
                    "error": (
                        f"Blast-radius guardrail blocked rollback for {inc_id} ({svc}): "
                        f"release {rel_id} is marked rollback_safe=False."
                    ),
                    "rejection": rejection,
                })

            if expected_stable and target_ver != expected_stable:
                rejection = {
                    "action": "execute_canary_rollback",
                    "incident_id": inc_id,
                    "service_name": svc,
                    "release_id": rel_id,
                    "target_stable_version": target_ver,
                    "expected_stable_version": expected_stable,
                    "reason": (
                        f"Target version '{target_ver}' does not match verified "
                        f"previous_stable_version '{expected_stable}' for {rel_id}."
                    ),
                    "rejected_at": datetime.now(timezone.utc).isoformat(),
                }
                state.setdefault("rejected_actions", []).append(rejection)
                _save_state(state)
                return json.dumps({
                    "status": "REJECTED",
                    "error": rejection["reason"],
                    "rejection": rejection,
                })

        rollbacks = state.setdefault("rollbacks", [])
        rb_id = f"RB-{1001 + len(rollbacks)}"
        record = {
            "rollback_id": rb_id,
            "incident_id": inc_id,
            "service_name": svc,
            "target_stable_version": target_ver,
            "reason": reason.strip(),
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "status": "ROLLED_BACK",
        }
        rollbacks.append(record)
        state.setdefault("incident_status_overrides", {})[inc_id] = "ROLLED_BACK"
        backend = _save_state(state)
        return json.dumps({
            "status": "ROLLED_BACK",
            "rollback_id": rb_id,
            "rollback": record,
            "state_backend": backend,
        })
    except Exception as exc:
        return json.dumps({"status": "ERROR", "error": str(exc)})


@mcp.tool()
def scale_service_replicas(
    service_name: str,
    cluster_region: str = "europe-west1",
    target_replicas: int = 6,
    reason: str = "SLO scaling adjustment",
) -> str:
    """Scale a service deployment replica count within the SRE safety corridor [3, 40].

    Args:
        service_name: Kubernetes service name (e.g. 'auth-token-gateway').
        cluster_region: Cluster region (e.g. 'europe-west1').
        target_replicas: Desired replica count (must be between 3 and 40; never 0).
        reason: Optional operational justification for scaling.

    Returns:
        JSON string confirming replica scaling or safety rejection if outside [3, 40].
    """
    try:
        rep = int(target_replicas)
        svc = service_name.strip().lower()
        min_safe, max_safe = _lookup_replica_corridor(svc)
        state = _load_state()
        if rep < min_safe or rep > max_safe:
            rejection = {
                "action": "scale_service_replicas",
                "service_name": svc,
                "cluster_region": cluster_region.strip(),
                "target_replicas": rep,
                "safe_corridor": [min_safe, max_safe],
                "reason": reason.strip() or "Replica count outside SLO runbook corridor.",
                "rejected_at": datetime.now(timezone.utc).isoformat(),
            }
            state.setdefault("rejected_actions", []).append(rejection)
            _save_state(state)
            return json.dumps({
                "status": "REJECTED",
                "guardrail": "REJECTED_REPLICA_GUARDRAIL",
                "error": (
                    f"target_replicas={rep} violates SRE availability guardrail "
                    f"[{min_safe}, {max_safe}] for {svc}."
                ),
                "rejection": rejection,
            })

        events = state.setdefault("scaling_events", [])
        scale_id = f"SCALE-{2001 + len(events)}"
        record = {
            "scale_id": scale_id,
            "service_name": svc,
            "cluster_region": cluster_region.strip(),
            "target_replicas": rep,
            "reason": reason.strip(),
            "scaled_at": datetime.now(timezone.utc).isoformat(),
            "status": "SCALED",
        }
        events.append(record)
        backend = _save_state(state)
        return json.dumps({
            "status": "SUCCESS",
            "scale_id": scale_id,
            "scaling_event": record,
            "state_backend": backend,
        })
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
        state = _load_state()
        updates = state.setdefault("incident_updates", [])
        inc_id = incident_id.strip().upper()
        status_norm = new_status.strip().upper()
        upd_id = f"TIMELINE-{3001 + len(updates)}"
        record = {
            "annotation_id": upd_id,
            "incident_id": inc_id,
            "remediation_summary": remediation_summary.strip(),
            "new_status": status_norm,
            "annotated_at": datetime.now(timezone.utc).isoformat(),
        }
        updates.append(record)
        state.setdefault("incident_status_overrides", {})[inc_id] = status_norm
        backend = _save_state(state)
        return json.dumps({
            "status": "SUCCESS",
            "annotation_id": upd_id,
            "annotation": record,
            "state_backend": backend,
        })
    except Exception as exc:
        return json.dumps({"status": "ERROR", "error": str(exc)})


@mcp.tool()
def emit_partner_service_advisory(
    incident_id: str,
    service_name: str,
    advisory_status: str = "DEGRADED",
    summary: str = "",
) -> str:
    """Emit a Tribe A2A service health advisory to Table 8 (Multi-Modal Travel Disruption Concierge).

    Correlates infrastructure outages on checkout, pricing, inventory, auth, or webhook services
    with disrupted travel itineraries in `seed_t08.disrupted_itineraries` so Table 8 can hold or
    resume passenger rebooking and hotel voucher checkout flows.

    Args:
        incident_id: Active incident ID (e.g. 'INC-0001').
        service_name: Affected microservice name (e.g. 'checkout-payment-svc').
        advisory_status: Service health state ('DEGRADED', 'MITIGATED', or 'ESCALATED').
        summary: Operational guidance for partner concierge agents.

    Returns:
        JSON string with the A2A advisory payload and correlated Table 8 itinerary counts.
    """
    try:
        inc_id = incident_id.strip().upper()
        svc = service_name.strip().lower()
        adv_status = advisory_status.strip().upper()
        project = (
            os.environ.get("GOOGLE_CLOUD_PROJECT")
            or os.environ.get("AGENT_ENGINE_PROJECT")
            or ""
        ).strip()

        itineraries: list[dict[str, Any]] = []
        t08_source = "local_csv_fallback"
        if project and "your-" not in project:
            try:
                from google.cloud import bigquery

                client = bigquery.Client(project=project)
                sql = f"""
                    SELECT itinerary_id, passenger_name, loyalty_tier, origin_airport,
                           destination_airport, disrupted_flight, disruption_type,
                           delay_minutes, hotel_booking_id, recovery_status
                    FROM `{project}.seed_t08.disrupted_itineraries`
                    WHERE recovery_status = 'UNRESOLVED'
                    ORDER BY delay_minutes DESC
                    LIMIT 5
                """
                itineraries = [dict(r.items()) for r in client.query(sql).result()]
                t08_source = f"bigquery:{project}.seed_t08.disrupted_itineraries"
            except Exception:
                itineraries = []

        if not itineraries:
            csv_rows = _read_csv_rows(_T08_DATA_DIR / "disrupted_itineraries.csv")
            pending = [r for r in csv_rows if r.get("recovery_status") == "UNRESOLVED"]
            pending.sort(key=lambda r: int(r.get("delay_minutes", 0) or 0), reverse=True)
            itineraries = pending[:5]

        service_impact_map = {
            "checkout-payment-svc": "Hotel voucher settlement & rebooking fee checkout",
            "realtime-pricing-engine": "Dynamic fare recalculation & upgrade waiver quotes",
            "inventory-reservation-svc": "Seat & partner hotel room inventory locks",
            "auth-token-gateway": "Loyalty tier authentication & passenger session tokens",
            "order-webhook-dispatcher": "Passenger SMS/push rebooking confirmation webhooks",
        }
        downstream_capability = service_impact_map.get(
            svc, "Partner travel rebooking & settlement pipeline"
        )

        state = _load_state()
        advisories = state.setdefault("partner_advisories", [])
        adv_id = f"A2A-T07-T08-{4001 + len(advisories)}"
        record = {
            "advisory_id": adv_id,
            "source_agent": "expedition_t07",
            "target_partner_table": "T08_travel_concierge",
            "incident_id": inc_id,
            "service_name": svc,
            "advisory_status": adv_status,
            "downstream_capability": downstream_capability,
            "summary": summary.strip() or f"{svc} is {adv_status} for incident {inc_id}.",
            "t08_data_source": t08_source,
            "impacted_itineraries_count": len(itineraries),
            "sample_disrupted_itineraries": itineraries[:3],
            "emitted_at": datetime.now(timezone.utc).isoformat(),
        }

        remote_engine = os.environ.get("T08_REASONING_ENGINE", "").strip()
        if remote_engine:
            record["remote_reasoning_engine"] = remote_engine

        advisories.append(record)
        backend = _save_state(state)
        return json.dumps({
            "status": "ADVISORY_EMITTED",
            "advisory_id": adv_id,
            "target_partner_table": "T08_travel_concierge",
            "impacted_itineraries_count": len(itineraries),
            "sample_disrupted_itineraries": itineraries[:3],
            "advisory": record,
            "state_backend": backend,
        })
    except Exception as exc:
        return json.dumps({"status": "ERROR", "error": str(exc)})


@mcp.tool()
def get_remediation_audit_log(service_name: str = "all") -> str:
    """Retrieve the stateful remediation audit log of rollbacks, scaling events, annotations, A2A advisories, and blocked attacks.

    Args:
        service_name: Filter by service name (e.g. 'checkout-payment-svc') or 'all' for all services.

    Returns:
        JSON string containing the remediation ledger and guardrail rejection history.
    """
    try:
        state = _load_state()
        svc_filter = service_name.strip().lower()

        def _match(item: dict[str, Any]) -> bool:
            if not svc_filter or svc_filter == "all":
                return True
            return str(item.get("service_name", "")).lower() == svc_filter

        rollbacks = [r for r in state.get("rollbacks", []) if _match(r)]
        scaling = [s for s in state.get("scaling_events", []) if _match(s)]
        annotations = state.get("incident_updates", [])
        advisories = [a for a in state.get("partner_advisories", []) if _match(a)]
        rejected = [x for x in state.get("rejected_actions", []) if _match(x)]

        return json.dumps({
            "status": "SUCCESS",
            "service_filter": svc_filter or "all",
            "summary_counts": {
                "rollbacks_executed": len(rollbacks),
                "scaling_events_executed": len(scaling),
                "timeline_annotations": len(annotations),
                "partner_advisories_emitted": len(advisories),
                "rejected_unsafe_or_injected_actions": len(rejected),
            },
            "rollbacks": rollbacks,
            "scaling_events": scaling,
            "incident_updates": annotations,
            "partner_advisories": advisories,
            "rejected_actions": rejected,
            "incident_status_overrides": state.get("incident_status_overrides", {}),
        })
    except Exception as exc:
        return json.dumps({"status": "ERROR", "error": str(exc)})


@mcp.resource("ui://sre-copilot/incident-dashboard")
def render_incident_dashboard() -> str:
    """Render an interactive HTML SRE War-Room & Blast-Radius Dashboard reflecting live remediation state."""
    state = _load_state()
    overrides = state.get("incident_status_overrides", {})
    incidents = _read_csv_rows(_DATA_DIR / "service_incidents.csv")[:12]
    rows_html = []
    for inc in incidents:
        inc_id = inc.get("incident_id", "")
        live_status = overrides.get(inc_id, inc.get("status", "OPEN"))
        badge_color = "#dc2626" if live_status == "OPEN" else ("#d97706" if live_status == "ESCALATED" else "#16a34a")
        rows_html.append(
            f"<tr>"
            f"<td><code>{inc_id}</code></td>"
            f"<td>{inc.get('service_name', '')}</td>"
            f"<td>{inc.get('severity', '')}</td>"
            f"<td>{inc.get('symptom_code', '')}</td>"
            f"<td>{inc.get('active_release_id', '')}</td>"
            f"<td><span style='background:{badge_color};color:#fff;padding:2px 8px;border-radius:12px;font-size:12px'>{live_status}</span></td>"
            f"</tr>"
        )
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
        "<title>Table 7 — Self-Healing Infrastructure &amp; Security Copilot</title>"
        "<style>body{font-family:system-ui,sans-serif;background:#0f172a;color:#f8fafc;padding:24px}"
        "table{width:100%;border-collapse:collapse;margin-top:16px}"
        "th,td{padding:10px;border-bottom:1px solid #334155;text-align:left}</style></head>"
        "<body><h1>Table 7: Self-Healing Infrastructure &amp; Security Copilot War-Room</h1>"
        f"<p>Rollbacks: {len(state.get('rollbacks', []))} | "
        f"Scaling Events: {len(state.get('scaling_events', []))} | "
        f"Blocked Attacks/Violations: {len(state.get('rejected_actions', []))} | "
        f"Tribe A2A Advisories (T08): {len(state.get('partner_advisories', []))}</p>"
        "<table><thead><tr><th>Incident</th><th>Service</th><th>Severity</th>"
        "<th>Symptom</th><th>Release</th><th>Live Status</th></tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody></table></body></html>"
    )


ACTION_TOOLS = [
    execute_canary_rollback,
    scale_service_replicas,
    annotate_incident_timeline,
    emit_partner_service_advisory,
    get_remediation_audit_log,
]
MCP_TOOLS = ACTION_TOOLS

if __name__ == "__main__":
    mcp.run(transport="stdio")
