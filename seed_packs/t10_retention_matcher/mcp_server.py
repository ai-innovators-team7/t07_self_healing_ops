"""FastMCP stdio server with Mock Action APIs for Table 10 (t10_retention_matcher)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("t10_retention_matcher_actions")

_PACK_DIR = Path(__file__).resolve().parent
_DEFAULT_STATE_PATH = _PACK_DIR / ".state.json"
_FALLBACK_STATE_PATH = Path("/tmp/t10_retention_matcher_state.json")


def _load_state() -> dict[str, Any]:
    for path in (_DEFAULT_STATE_PATH, _FALLBACK_STATE_PATH):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return {"dispatched_offers": [], "csm_playbooks": [], " suppressed_accounts": []}


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
def dispatch_retention_offer(
    subscriber_id: str,
    offer_id: str,
    discount_pct: int,
    credit_eur: float = 0.0,
) -> str:
    """Dispatch a personalized save offer to an at-risk subscriber (max 35% discount, max 150 EUR credit).

    Args:
        subscriber_id: Subscriber ID (e.g. 'SUB-0001').
        offer_id: Retention offer ID from catalog (e.g. 'OFR-001').
        discount_pct: Promotional discount percentage (must be <= 35%).
        credit_eur: Optional account credit in EUR (must be <= 150.0 EUR).

    Returns:
        JSON string confirming the dispatched retention offer or policy rejection.
    """
    disc = int(discount_pct)
    cred = float(credit_eur)
    if disc < 0 or disc > 35 or cred < 0.0 or cred > 150.0:
        return json.dumps({
            "status": "REJECTED_MARGIN_GUARDRAIL",
            "error": (
                f"discount_pct={disc}% / credit_eur=€{cred} violates retention guardrail "
                f"(max 35% discount, max €150.00 credit)."
            ),
        })
    state = _load_state()
    offers = state.setdefault("dispatched_offers", [])
    disp_id = f"SAVE-{1001 + len(offers)}"
    record = {
        "dispatch_id": disp_id,
        "subscriber_id": subscriber_id.strip(),
        "offer_id": offer_id.strip(),
        "discount_pct": disc,
        "credit_eur": round(cred, 2),
        "dispatched_at": datetime.now(timezone.utc).isoformat(),
        "status": "SENT",
    }
    offers.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "save_offer": record, "state_backend": backend})


@mcp.tool()
def schedule_onboarding_rescue_call(
    subscriber_id: str,
    product_specialist_topic: str,
    priority: str = "HIGH",
) -> str:
    """Schedule a zero-discount Customer Success onboarding rescue session for low-adoption accounts.

    Args:
        subscriber_id: Subscriber ID (e.g. 'SUB-0002').
        product_specialist_topic: Adoption workflow to coach (e.g. 'Team_Templates_Automation').
        priority: Call priority ('STANDARD', 'HIGH').

    Returns:
        JSON string confirming the scheduled CSM rescue call.
    """
    state = _load_state()
    playbooks = state.setdefault("csm_playbooks", [])
    call_id = f"CSM-{2001 + len(playbooks)}"
    record = {
        "csm_call_id": call_id,
        "subscriber_id": subscriber_id.strip(),
        "product_specialist_topic": product_specialist_topic.strip(),
        "priority": priority.strip().upper(),
        "scheduled_at": datetime.now(timezone.utc).isoformat(),
        "status": "BOOKED",
    }
    playbooks.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "csm_rescue": record, "state_backend": backend})


@mcp.tool()
def log_churn_prevention_decision(
    subscriber_id: str,
    decision_type: str,
    expected_net_ltv_impact_eur: float,
) -> str:
    """Record a retention decision (e.g., 'NO_DISCOUNT_NEEDED', 'OFFER_SENT', 'ESCALATED_TO_CSM') in the audit log.

    Args:
        subscriber_id: Subscriber ID (e.g. 'SUB-0001').
        decision_type: Decision label ('NO_DISCOUNT_NEEDED', 'OFFER_SENT', 'ESCALATED_TO_CSM').
        expected_net_ltv_impact_eur: Estimated net LTV preserved in EUR.

    Returns:
        JSON string confirming the logged retention decision.
    """
    state = _load_state()
    decisions = state.setdefault("logged_decisions", [])
    dec_id = f"RETDEC-{3001 + len(decisions)}"
    record = {
        "decision_id": dec_id,
        "subscriber_id": subscriber_id.strip(),
        "decision_type": decision_type.strip().upper(),
        "expected_net_ltv_impact_eur": round(float(expected_net_ltv_impact_eur), 2),
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }
    decisions.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "decision": record, "state_backend": backend})


ACTION_TOOLS = [
    dispatch_retention_offer,
    schedule_onboarding_rescue_call,
    log_churn_prevention_decision,
]
MCP_TOOLS = ACTION_TOOLS

if __name__ == "__main__":
    mcp.run(transport="stdio")
