"""Reference Seed Pack (t00_example) — FastMCP stdio server for Mock Action APIs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from mcp.server.mcpserver import MCPServer as FastMCP  # type: ignore[no-redef]

mcp = FastMCP("t00_coffee_actions")

_PACK_DIR = Path(__file__).resolve().parent
_DEFAULT_STATE_PATH = _PACK_DIR / ".state.json"
_FALLBACK_STATE_PATH = Path("/tmp/t00_example_state.json")


def _load_state() -> dict[str, Any]:
    for path in (_DEFAULT_STATE_PATH, _FALLBACK_STATE_PATH):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {"reorders": []}


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
def submit_bean_reorder(
    bean_origin: str,
    bags_kg: int,
    urgency: str = "standard",
) -> str:
    """Submit a mock coffee bean or café supply restock order to the roastery warehouse.

    Args:
        bean_origin: Name of the coffee bean origin or supply item (e.g. 'Ethiopian Yirgacheffe', 'Colombian Huila').
        bags_kg: Quantity to order in kilogram bags (must be between 1 and 500).
        urgency: Delivery urgency level ('standard', 'express', or 'same_day').

    Returns:
        JSON string containing the order confirmation ID, estimated delivery, and persisted state status.
    """
    try:
        if not bean_origin or not bean_origin.strip():
            return json.dumps({
                "status": "INVALID_ARGUMENT",
                "error": "bean_origin is required.",
            })
        qty = int(bags_kg)
        if qty <= 0 or qty > 500:
            return json.dumps({
                "status": "INVALID_ARGUMENT",
                "error": f"bags_kg must be between 1 and 500 (got {qty}).",
            })
        normalized_urgency = urgency.strip().lower() if urgency else "standard"
        if normalized_urgency not in {"standard", "express", "same_day"}:
            normalized_urgency = "standard"

        state = _load_state()
        reorders = state.setdefault("reorders", [])
        order_id = f"ROAST-{1001 + len(reorders)}"
        unit_cost_gbp = 14.50
        record = {
            "order_id": order_id,
            "bean_origin": bean_origin.strip(),
            "bags_kg": qty,
            "urgency": normalized_urgency,
            "estimated_total_gbp": round(qty * unit_cost_gbp, 2),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "CONFIRMED",
        }
        reorders.append(record)
        saved_to = _save_state(state)
        return json.dumps({
            "status": "SUCCESS",
            "order": record,
            "state_backend": saved_to,
        })
    except Exception as exc:
        return json.dumps({
            "status": "ERROR",
            "error": str(exc),
        })


MCP_TOOLS = [submit_bean_reorder]


if __name__ == "__main__":
    mcp.run(transport="stdio")
