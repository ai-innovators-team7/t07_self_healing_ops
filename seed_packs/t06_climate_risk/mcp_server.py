"""FastMCP stdio server with Mock Action APIs for Table 6 (t06_climate_risk)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("t06_climate_risk_actions")

_PACK_DIR = Path(__file__).resolve().parent
_DEFAULT_STATE_PATH = _PACK_DIR / ".state.json"
_FALLBACK_STATE_PATH = Path("/tmp/t06_climate_risk_state.json")


def _load_state() -> dict[str, Any]:
    for path in (_DEFAULT_STATE_PATH, _FALLBACK_STATE_PATH):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return {"renewal_quotes": [], "engineering_inspections": [], "cat_alerts": []}


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
def issue_renewal_quote_adjustment(
    asset_id: str,
    premium_loading_pct: float,
    recommended_deductible_eur: float,
    mitigation_requirement: str,
) -> str:
    """Issue a climate-adjusted commercial renewal quote (loading bounded between -15% and +75%).

    Args:
        asset_id: Insured asset ID (e.g. 'AST-0001').
        premium_loading_pct: Technical rate loading percentage (bounded between -15.0 and +75.0).
        recommended_deductible_eur: Updated deductible in EUR.
        mitigation_requirement: Required physical resilience measure for bind.

    Returns:
        JSON string with renewal quote ID or underwriting bound rejection.
    """
    loading = float(premium_loading_pct)
    if loading < -15.0 or loading > 75.0:
        return json.dumps({
            "status": "REJECTED_ACTUARIAL_BOUND",
            "error": f"premium_loading_pct={loading}% violates underwriting corridor [-15.0%, +75.0%].",
        })
    state = _load_state()
    quotes = state.setdefault("renewal_quotes", [])
    quote_id = f"RNW-{1001 + len(quotes)}"
    record = {
        "quote_id": quote_id,
        "asset_id": asset_id.strip(),
        "premium_loading_pct": round(loading, 2),
        "recommended_deductible_eur": round(float(recommended_deductible_eur), 2),
        "mitigation_requirement": mitigation_requirement.strip(),
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "status": "ISSUED",
    }
    quotes.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "renewal_quote": record, "state_backend": backend})


@mcp.tool()
def trigger_loss_prevention_inspection(
    asset_id: str,
    hazard_focus: str,
    priority_level: str = "HIGH",
) -> str:
    """Dispatch a field risk-engineering loss prevention inspection for a high-exposure asset.

    Args:
        asset_id: Insured asset ID (e.g. 'AST-0031').
        hazard_focus: Primary physical hazard to inspect (e.g. 'Flash_Flood', 'Extreme_Heatwave').
        priority_level: Inspection urgency ('STANDARD', 'HIGH', 'CRITICAL').

    Returns:
        JSON string confirming the scheduled inspection work order.
    """
    state = _load_state()
    inspections = state.setdefault("engineering_inspections", [])
    insp_id = f"INSP-{2001 + len(inspections)}"
    record = {
        "inspection_id": insp_id,
        "asset_id": asset_id.strip(),
        "hazard_focus": hazard_focus.strip(),
        "priority_level": priority_level.strip().upper(),
        "scheduled_at": datetime.now(timezone.utc).isoformat(),
        "status": "DISPATCHED",
    }
    inspections.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "inspection": record, "state_backend": backend})


@mcp.tool()
def register_catastrophe_accumulation_alert(
    region: str,
    total_exposed_eur: float,
    reinsurance_layer: str,
) -> str:
    """Register a regional catastrophe accumulation alert with treaty reinsurance management.

    Args:
        region: Geographic region code (e.g. 'ES_Valencia_Coast').
        total_exposed_eur: Total insured value exposed in EUR.
        reinsurance_layer: Reinsurance treaty layer triggered (e.g. 'Cat_XL_Layer_2').

    Returns:
        JSON string confirming the catastrophe accumulation alert.
    """
    state = _load_state()
    alerts = state.setdefault("cat_alerts", [])
    alert_id = f"CAT-{3001 + len(alerts)}"
    record = {
        "alert_id": alert_id,
        "region": region.strip(),
        "total_exposed_eur": round(float(total_exposed_eur), 2),
        "reinsurance_layer": reinsurance_layer.strip(),
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "status": "ACTIVE",
    }
    alerts.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "cat_alert": record, "state_backend": backend})


ACTION_TOOLS = [
    issue_renewal_quote_adjustment,
    trigger_loss_prevention_inspection,
    register_catastrophe_accumulation_alert,
]
MCP_TOOLS = ACTION_TOOLS

if __name__ == "__main__":
    mcp.run(transport="stdio")
