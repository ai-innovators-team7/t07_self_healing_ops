"""FastMCP stdio server with Mock Action APIs for Table 1 (t01_campaign_orchestrator)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("t01_campaign_orchestrator_actions")

_PACK_DIR = Path(__file__).resolve().parent
_DEFAULT_STATE_PATH = _PACK_DIR / ".state.json"
_FALLBACK_STATE_PATH = Path("/tmp/t01_campaign_orchestrator_state.json")


def _load_state() -> dict[str, Any]:
    for path in (_DEFAULT_STATE_PATH, _FALLBACK_STATE_PATH):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return {"bids": [], "localized_variants": [], "paused_variants": []}


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
def place_ad_bid(
    variant_id: str,
    channel: str,
    new_cpm_bid_eur: float,
    daily_budget_eur: float = 500.0,
) -> str:
    """Update programmatic CPM bid and daily budget for an ad variant on an ad network.

    Args:
        variant_id: Ad variant identifier (e.g. 'VAR-0001').
        channel: Ad network channel (e.g. 'Meta_Reels', 'TikTok_Pulse', 'YouTube_Shorts').
        new_cpm_bid_eur: New target CPM bid in EUR (policy cap: 0.50 to 25.00 EUR).
        daily_budget_eur: Daily spend cap in EUR (policy cap: 50.0 to 5000.0 EUR).

    Returns:
        JSON string confirming the bid update ID or policy rejection.
    """
    if new_cpm_bid_eur <= 0.0 or new_cpm_bid_eur > 25.0:
        return json.dumps({
            "status": "REJECTED_POLICY_CAP",
            "error": f"new_cpm_bid_eur={new_cpm_bid_eur} violates the 25.00 EUR max CPM guardrail.",
        })
    if daily_budget_eur <= 0.0 or daily_budget_eur > 5000.0:
        return json.dumps({
            "status": "REJECTED_POLICY_CAP",
            "error": f"daily_budget_eur={daily_budget_eur} violates the 5000.00 EUR daily budget cap.",
        })
    state = _load_state()
    bids = state.setdefault("bids", [])
    bid_id = f"BID-{1001 + len(bids)}"
    record = {
        "bid_id": bid_id,
        "variant_id": variant_id.strip(),
        "channel": channel.strip(),
        "new_cpm_bid_eur": round(float(new_cpm_bid_eur), 2),
        "daily_budget_eur": round(float(daily_budget_eur), 2),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ACTIVE_BID",
    }
    bids.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "bid": record, "state_backend": backend})


@mcp.tool()
def create_localized_variant(
    event_id: str,
    locale: str,
    headline: str,
    visual_prompt: str,
    cta_text: str = "Book Tickets Now",
) -> str:
    """Register a new localized ad creative variant for a live event.

    Args:
        event_id: Event identifier (e.g. 'EVT-0001').
        locale: Target locale code (e.g. 'en-GB', 'es-ES', 'it-IT').
        headline: Localized ad headline text.
        visual_prompt: Prompt describing the visual asset scene.
        cta_text: Call-to-action button text.

    Returns:
        JSON string with the created variant ID and review status.
    """
    state = _load_state()
    variants = state.setdefault("localized_variants", [])
    new_var_id = f"VAR-LOC-{2001 + len(variants)}"
    record = {
        "variant_id": new_var_id,
        "event_id": event_id.strip(),
        "locale": locale.strip(),
        "headline": headline.strip(),
        "visual_prompt": visual_prompt.strip(),
        "cta_text": cta_text.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "STAGED_FOR_SERVING",
    }
    variants.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "variant": record, "state_backend": backend})


@mcp.tool()
def pause_ad_variant(variant_id: str, reason: str) -> str:
    """Pause an underperforming or non-compliant ad variant immediately.

    Args:
        variant_id: Ad variant identifier (e.g. 'VAR-0013').
        reason: Reason for pausing (e.g. 'low ROAS below 1.0', 'flagged prompt injection').

    Returns:
        JSON string with pause confirmation details.
    """
    state = _load_state()
    paused = state.setdefault("paused_variants", [])
    pause_id = f"PAUSE-{3001 + len(paused)}"
    record = {
        "pause_id": pause_id,
        "variant_id": variant_id.strip(),
        "reason": reason.strip(),
        "paused_at": datetime.now(timezone.utc).isoformat(),
        "status": "PAUSED",
    }
    paused.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "paused": record, "state_backend": backend})


ACTION_TOOLS = [place_ad_bid, create_localized_variant, pause_ad_variant]
MCP_TOOLS = ACTION_TOOLS

if __name__ == "__main__":
    mcp.run(transport="stdio")
