"""FastMCP stdio server with Mock Action APIs for Table 2 (t02_dynamic_storefronts)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("t02_dynamic_storefronts_actions")

_PACK_DIR = Path(__file__).resolve().parent
_DEFAULT_STATE_PATH = _PACK_DIR / ".state.json"
_FALLBACK_STATE_PATH = Path("/tmp/t02_dynamic_storefronts_state.json")


def _load_state() -> dict[str, Any]:
    for path in (_DEFAULT_STATE_PATH, _FALLBACK_STATE_PATH):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return {"published_layouts": [], "render_queue": [], "promo_banners": []}


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
def publish_storefront_layout(
    segment_id: str,
    featured_skus: str,
    hero_headline: str,
    theme_style: str = "Nordic_Minimal",
) -> str:
    """Publish a personalized dynamic storefront layout for an audience segment.

    Args:
        segment_id: Target audience segment ID (e.g. 'SEG-001').
        featured_skus: Comma-separated list of SKU IDs to feature (e.g. 'SKU-0001,SKU-0006').
        hero_headline: Headline displayed in the storefront hero banner.
        theme_style: Visual style theme (e.g. 'Nordic_Minimal', 'Mediterranean_Warm').

    Returns:
        JSON string confirming the published layout ID and live status.
    """
    state = _load_state()
    layouts = state.setdefault("published_layouts", [])
    layout_id = f"LAYOUT-{1001 + len(layouts)}"
    record = {
        "layout_id": layout_id,
        "segment_id": segment_id.strip(),
        "featured_skus": [s.strip() for s in featured_skus.split(",") if s.strip()],
        "hero_headline": hero_headline.strip(),
        "theme_style": theme_style.strip(),
        "published_at": datetime.now(timezone.utc).isoformat(),
        "status": "LIVE",
    }
    layouts.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "layout": record, "state_backend": backend})


@mcp.tool()
def queue_visual_asset_render(
    sku_id: str,
    scene_prompt: str,
    aspect_ratio: str = "16:9",
) -> str:
    """Queue a generative visual asset render job for a catalog SKU.

    Args:
        sku_id: Catalog SKU ID (e.g. 'SKU-0003').
        scene_prompt: Descriptive scene prompt for lifestyle rendering.
        aspect_ratio: Target aspect ratio ('16:9', '1:1', or '9:16').

    Returns:
        JSON string with render job ID and queue status.
    """
    state = _load_state()
    queue = state.setdefault("render_queue", [])
    job_id = f"RENDER-{2001 + len(queue)}"
    record = {
        "render_job_id": job_id,
        "sku_id": sku_id.strip(),
        "scene_prompt": scene_prompt.strip(),
        "aspect_ratio": aspect_ratio.strip(),
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "status": "QUEUED",
    }
    queue.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "render_job": record, "state_backend": backend})


@mcp.tool()
def update_promo_banner(
    segment_id: str,
    discount_pct: int,
    banner_copy: str,
) -> str:
    """Update the promotional discount banner for an audience segment (max 30% discount policy).

    Args:
        segment_id: Target audience segment ID (e.g. 'SEG-002').
        discount_pct: Promotional discount percentage (must be between 5 and 30).
        banner_copy: Promotional banner text shown to shoppers.

    Returns:
        JSON string confirming the banner activation or policy rejection if discount > 30%.
    """
    disc = int(discount_pct)
    if disc < 0 or disc > 30:
        return json.dumps({
            "status": "REJECTED_POLICY_CAP",
            "error": f"discount_pct={disc}% exceeds the 30% maximum automated merchandising discount policy.",
        })
    state = _load_state()
    banners = state.setdefault("promo_banners", [])
    banner_id = f"PROMO-{3001 + len(banners)}"
    record = {
        "banner_id": banner_id,
        "segment_id": segment_id.strip(),
        "discount_pct": disc,
        "banner_copy": banner_copy.strip(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ACTIVE",
    }
    banners.append(record)
    backend = _save_state(state)
    return json.dumps({"status": "SUCCESS", "promo_banner": record, "state_backend": backend})


ACTION_TOOLS = [publish_storefront_layout, queue_visual_asset_render, update_promo_banner]
MCP_TOOLS = ACTION_TOOLS

if __name__ == "__main__":
    mcp.run(transport="stdio")
