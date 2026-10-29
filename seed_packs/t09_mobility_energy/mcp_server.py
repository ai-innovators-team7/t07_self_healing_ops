"""FastMCP stdio server with Mock Action APIs for Table 9 (t09_mobility_energy)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("t09_mobility_energy_actions")

_PACK_DIR = Path(__file__).resolve().parent
_DEFAULT_STATE_PATH = _PACK_DIR / ".state.json"
_FALLBACK_STATE_PATH = Path("/tmp/t09_mobility_energy_state.json")


def _load_state() -> dict[str, Any]:
    for path in (_DEFAULT_STATE_PATH, _FALLBACK_STATE_PATH):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return {"charging_schedules": [], "v2g_dispatches": [], "load_caps": []}


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
def schedule_smart_charging_plan(
    depot_id: str,
    vehicle_ids: str,
    window_id: str,
    target_soc_pct: int = 85,
) -> str:
    """Schedule a smart EV charging plan aligned with a low-tariff, low-carbon grid window.

    Args:
        depot_id: Depot identifier (e.g. 'DEP-LONDON-EAST', 'DEP-MADRID-SOUTH').
        vehicle_ids: Comma-separated EV IDs (e.g. 'EV-0001,EV-0006').
        window_id: Grid tariff window ID (e.g. 'WIN-002').
        target_soc_pct: Target battery State of Charge percentage (default 85).

    Returns:
        JSON string confirming the scheduled charging plan.
    """
    state = _load_state()
    plans = state.setdefault("charging_schedules", [])
    plan_id = f"CHG-{1001 + len(plans)}"
    record = {
        "plan_id": plan_id,
        "depot_id": depot_id.strip(),
        "vehicle_ids": [v.strip() for v in vehicle_ids.split(",") if v.strip()],
        "window_id": window_id.strip(),
        "target_soc_pct": int(target_soc_pct),
        "scheduled_at": datetime.now(timezone.utc).isoformat(),
        "status": "SCHEDULED",
    }
    plans.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "charging_plan": record, "state_backend": backend})


@mcp.tool()
def authorize_v2g_grid_discharge(
    depot_id: str,
    window_id: str,
    export_kw: float,
    min_reserve_soc_pct: int = 35,
) -> str:
    """Authorize Vehicle-to-Grid (V2G) peak shaving export (enforces >=30% minimum battery reserve).

    Args:
        depot_id: Depot ID (e.g. 'DEP-MADRID-SOUTH').
        window_id: Peak tariff window ID (e.g. 'WIN-018').
        export_kw: Total power in kW to export back to the grid.
        min_reserve_soc_pct: Minimum battery SoC floor to preserve morning route readiness (must be >= 30%).

    Returns:
        JSON string confirming V2G discharge or safety rejection if min_reserve_soc_pct < 30%.
    """
    reserve = int(min_reserve_soc_pct)
    if reserve < 30:
        return json.dumps({
            "status": "REJECTED_SOC_SAFETY_FLOOR",
            "error": f"min_reserve_soc_pct={reserve}% violates the 30% minimum fleet route reserve policy.",
        })
    state = _load_state()
    dispatches = state.setdefault("v2g_dispatches", [])
    v2g_id = f"V2G-{2001 + len(dispatches)}"
    record = {
        "v2g_dispatch_id": v2g_id,
        "depot_id": depot_id.strip(),
        "window_id": window_id.strip(),
        "export_kw": round(float(export_kw), 2),
        "min_reserve_soc_pct": reserve,
        "authorized_at": datetime.now(timezone.utc).isoformat(),
        "status": "AUTHORIZED",
    }
    dispatches.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "v2g_dispatch": record, "state_backend": backend})


@mcp.tool()
def throttle_depot_transformer_load(
    depot_id: str,
    max_site_load_kw: float,
    reason: str,
) -> str:
    """Apply an automated site load cap to protect a depot transformer from thermal overload.

    Args:
        depot_id: Depot ID (e.g. 'DEP-LONDON-EAST').
        max_site_load_kw: Maximum site load ceiling in kW.
        reason: Engineering justification for load throttling.

    Returns:
        JSON string confirming the active transformer load cap.
    """
    state = _load_state()
    caps = state.setdefault("load_caps", [])
    cap_id = f"CAP-{3001 + len(caps)}"
    record = {
        "load_cap_id": cap_id,
        "depot_id": depot_id.strip(),
        "max_site_load_kw": round(float(max_site_load_kw), 2),
        "reason": reason.strip(),
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "status": "ACTIVE",
    }
    caps.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "load_cap": record, "state_backend": backend})


ACTION_TOOLS = [
    schedule_smart_charging_plan,
    authorize_v2g_grid_discharge,
    throttle_depot_transformer_load,
]
MCP_TOOLS = ACTION_TOOLS

if __name__ == "__main__":
    mcp.run(transport="stdio")
