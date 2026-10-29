"""ADK Function Tools for Seed Pack t02_dynamic_storefronts (BigQuery + Mock Actions)."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from google.cloud import bigquery
from seed_packs.t02_dynamic_storefronts.mcp_server import (
    ACTION_TOOLS,
    publish_storefront_layout,
    queue_visual_asset_render,
    update_promo_banner,
)

_DATA_DIR = Path(__file__).resolve().parent / "data"
_DEFAULT_DATASET = "seed_t02"


def _resolve_project_and_dataset() -> tuple[str, str]:
    """Resolve project and dataset at call time; '' project means "not configured"."""
    project = (
        os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("AGENT_ENGINE_PROJECT")
        or ""
    ).strip()
    if "your-gcp-project-id" in project.lower() or "your-project-id" in project.lower():
        project = ""
    dataset = os.environ.get("SEED_BQ_DATASET", _DEFAULT_DATASET).strip() or _DEFAULT_DATASET
    return project, dataset


def _offline_reason(project: str) -> str:
    """Explain why BigQuery was skipped and what to do about it."""
    if not project:
        return (
            "GOOGLE_CLOUD_PROJECT (or AGENT_ENGINE_PROJECT) is not set, so these rows come "
            "from the bundled CSV copy. Set GOOGLE_CLOUD_PROJECT in .env and run "
            "`make seed PACK=t02` to query BigQuery."
        )
    return "SEED_OFFLINE_MODE enabled: rows come from the bundled CSV copy."


def _bq_error_hint(exc: Exception) -> str:
    """Turn a BigQuery failure into an actionable fallback reason."""
    return (
        f"BigQuery query failed ({type(exc).__name__}: {exc}). These rows come from the "
        "bundled CSV copy. If the dataset is missing run `make seed PACK=t02`; if "
        "credentials are missing run `gcloud auth application-default login`."
    )


def _read_local_csv(name: str) -> list[dict[str, Any]]:
    path = _DATA_DIR / f"{name}.csv"
    with path.open("r", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def find_catalog_products(
    category: str = "all",
    style_theme: str = "all",
    min_stock: int = 10,
) -> str:
    """Search catalog products in BigQuery by category, style theme, and minimum stock level.

    Args:
        category: Product category (e.g. 'Modular_Sofas', 'Smart_Lighting', 'Ergonomic_Desks', or 'all').
        style_theme: Style theme (e.g. 'Nordic_Minimal', 'Mediterranean_Warm', or 'all').
        min_stock: Minimum stock quantity required (default 10).

    Returns:
        JSON string with matching products sorted by highest margin percentage.
    """
    project, dataset = _resolve_project_and_dataset()
    cat_clean = (category or "all").strip()
    style_clean = (style_theme or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.products_catalog`"
            clauses = ["stock_qty >= @min_stock"]
            params: list[Any] = [bigquery.ScalarQueryParameter("min_stock", "INT64", int(min_stock))]
            if cat_clean.lower() != "all":
                clauses.append("LOWER(category) = LOWER(@cat)")
                params.append(bigquery.ScalarQueryParameter("cat", "STRING", cat_clean))
            if style_clean.lower() != "all":
                clauses.append("LOWER(style_theme) = LOWER(@style)")
                params.append(bigquery.ScalarQueryParameter("style", "STRING", style_clean))
            where_sql = " AND ".join(clauses)
            sql = (
                f"SELECT sku_id, product_name, category, style_theme, base_price_eur, "
                f"stock_qty, margin_pct, hero_asset_status, description "
                f"FROM {table_ref} WHERE {where_sql} ORDER BY margin_pct DESC LIMIT 15"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.products_catalog",
                "count": len(rows),
                "products": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("products_catalog")
        if int(r["stock_qty"]) >= int(min_stock)
        and (cat_clean.lower() == "all" or r["category"].lower() == cat_clean.lower())
        and (style_clean.lower() == "all" or r["style_theme"].lower() == style_clean.lower())
    ]
    rows.sort(key=lambda r: float(r["margin_pct"]), reverse=True)
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows[:15]),
        "products": rows[:15],
    })


def get_storefront_performance(segment_id: str = "SEG-001", limit: int = 10) -> str:
    """Query storefront experiment performance (views, add-to-cart, purchases, bounce rate) from BigQuery.

    Args:
        segment_id: Audience segment ID (e.g. 'SEG-001' or 'all').
        limit: Max rows to return (default 10).

    Returns:
        JSON string with storefront experiment metrics for the requested segment.
    """
    project, dataset = _resolve_project_and_dataset()
    seg_clean = (segment_id or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.storefront_experiments`"
            params: list[Any] = [bigquery.ScalarQueryParameter("lim", "INT64", int(limit))]
            where_sql = ""
            if seg_clean.lower() != "all":
                where_sql = "WHERE LOWER(segment_id) = LOWER(@seg) "
                params.append(bigquery.ScalarQueryParameter("seg", "STRING", seg_clean))
            sql = (
                f"SELECT experiment_id, segment_id, sku_id, layout_variant, hero_headline, "
                f"views, add_to_cart_count, purchases, bounce_rate_pct "
                f"FROM {table_ref} {where_sql}ORDER BY purchases DESC LIMIT @lim"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.storefront_experiments",
                "segment_id": seg_clean,
                "count": len(rows),
                "experiments": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("storefront_experiments")
        if seg_clean.lower() == "all" or r["segment_id"].lower() == seg_clean.lower()
    ][: int(limit)]
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows),
        "experiments": rows,
    })


def get_audience_segments(region: str = "all") -> str:
    """Query audience segments, preferred style themes, AOV, and conversion rates from BigQuery.

    Args:
        region: Region filter (e.g. 'UK_London', 'ES_Madrid', 'ES_Barcelona', or 'all').

    Returns:
        JSON string listing audience segments ordered by conversion rate.
    """
    project, dataset = _resolve_project_and_dataset()
    reg_clean = (region or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.audience_segments`"
            params: list[Any] = []
            where_sql = ""
            if reg_clean.lower() != "all":
                where_sql = "WHERE LOWER(region) = LOWER(@reg) "
                params.append(bigquery.ScalarQueryParameter("reg", "STRING", reg_clean))
            sql = (
                f"SELECT segment_id, segment_name, region, preferred_style, device_type, "
                f"avg_order_value_eur, conversion_rate_pct "
                f"FROM {table_ref} {where_sql}ORDER BY conversion_rate_pct DESC LIMIT 20"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.audience_segments",
                "region": reg_clean,
                "count": len(rows),
                "segments": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("audience_segments")
        if reg_clean.lower() == "all" or r["region"].lower() == reg_clean.lower()
    ][:20]
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows),
        "segments": rows,
    })


TOOLS = [
    find_catalog_products,
    get_storefront_performance,
    get_audience_segments,
]

__all__ = [
    "TOOLS",
    "ACTION_TOOLS",
    "find_catalog_products",
    "get_storefront_performance",
    "get_audience_segments",
    "publish_storefront_layout",
    "queue_visual_asset_render",
    "update_promo_banner",
]
