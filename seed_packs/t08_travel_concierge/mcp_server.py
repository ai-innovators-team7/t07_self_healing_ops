"""FastMCP stdio server with Mock Action APIs for Table 8 (t08_travel_concierge)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("t08_travel_concierge_actions")

_PACK_DIR = Path(__file__).resolve().parent
_DEFAULT_STATE_PATH = _PACK_DIR / ".state.json"
_FALLBACK_STATE_PATH = Path("/tmp/t08_travel_concierge_state.json")


def _load_state() -> dict[str, Any]:
    for path in (_DEFAULT_STATE_PATH, _FALLBACK_STATE_PATH):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return {"rebookings": [], "hotel_holds": [], "vouchers": []}


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
def rebook_passenger_segment(
    itinerary_id: str,
    option_id: str,
    waive_fare_difference: bool = True,
) -> str:
    """Confirm an alternative flight or high-speed rail rebooking for a disrupted itinerary.

    Args:
        itinerary_id: Disrupted itinerary ID (e.g. 'ITIN-0001').
        option_id: Replacement inventory option ID (e.g. 'OPT-0001').
        waive_fare_difference: Whether to waive fare difference under IROPS policy.

    Returns:
        JSON string confirming the new PNR segment status.
    """
    state = _load_state()
    rebookings = state.setdefault("rebookings", [])
    reb_id = f"REBK-{1001 + len(rebookings)}"
    record = {
        "rebooking_id": reb_id,
        "itinerary_id": itinerary_id.strip(),
        "option_id": option_id.strip(),
        "waive_fare_difference": bool(waive_fare_difference),
        "rebooked_at": datetime.now(timezone.utc).isoformat(),
        "status": "CONFIRMED",
    }
    rebookings.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "rebooking": record, "state_backend": backend})


@mcp.tool()
def sync_hotel_late_checkin(
    itinerary_id: str,
    hotel_id: str,
    estimated_arrival_iso: str,
) -> str:
    """Guarantee late check-in or overnight IROPS room hold with a partner hotel.

    Args:
        itinerary_id: Passenger itinerary ID (e.g. 'ITIN-0001').
        hotel_id: Partner hotel ID (e.g. 'HTL-001').
        estimated_arrival_iso: Updated estimated arrival timestamp in ISO-8601 format.

    Returns:
        JSON string confirming the guaranteed late check-in hold.
    """
    state = _load_state()
    holds = state.setdefault("hotel_holds", [])
    hold_id = f"HHOLD-{2001 + len(holds)}"
    record = {
        "hotel_hold_id": hold_id,
        "itinerary_id": itinerary_id.strip(),
        "hotel_id": hotel_id.strip(),
        "estimated_arrival_iso": estimated_arrival_iso.strip(),
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "status": "GUARANTEED_LATE_ARRIVAL",
    }
    holds.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "hotel_hold": record, "state_backend": backend})


@mcp.tool()
def issue_compensation_voucher(
    itinerary_id: str,
    amount_eur: float,
    reason_code: str,
) -> str:
    """Issue an EU261 / disruption hospitality voucher (capped at 600 EUR automated limit).

    Args:
        itinerary_id: Disrupted itinerary ID (e.g. 'ITIN-0001').
        amount_eur: Compensation voucher amount in EUR (must not exceed 600.0 EUR).
        reason_code: Reason code (e.g. 'EU261_DELAY_4H', 'OVERNIGHT_MEAL_CARE').

    Returns:
        JSON string with voucher details or policy rejection if amount > 600 EUR.
    """
    amt = float(amount_eur)
    if amt <= 0 or amt > 600.0:
        return json.dumps({
            "status": "REJECTED_VOUCHER_CAP",
            "error": f"amount_eur={amt} violates the €600.00 EU261 automated compensation ceiling.",
        })
    state = _load_state()
    vouchers = state.setdefault("vouchers", [])
    v_id = f"VCH-{3001 + len(vouchers)}"
    record = {
        "voucher_id": v_id,
        "itinerary_id": itinerary_id.strip(),
        "amount_eur": round(amt, 2),
        "reason_code": reason_code.strip(),
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "status": "ISSUED",
    }
    vouchers.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "voucher": record, "state_backend": backend})


ACTION_TOOLS = [
    rebook_passenger_segment,
    sync_hotel_late_checkin,
    issue_compensation_voucher,
]
MCP_TOOLS = ACTION_TOOLS

if __name__ == "__main__":
    mcp.run(transport="stdio")
