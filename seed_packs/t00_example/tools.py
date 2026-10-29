"""Reference Seed Pack (t00_example) — ADK Function Tools backed by BigQuery (with local JSON fallback)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from seed_packs.t00_example.mcp_server import submit_bean_reorder

_DATA_DIR = Path(__file__).resolve().parent / "data"
_DEFAULT_DATASET = "seed_t00"


def _resolve_project_and_dataset() -> tuple[str, str]:
    """Resolve project and dataset at call time (never at import time)."""
    project = (
        os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("AGENT_ENGINE_PROJECT")
        or ""
    ).strip()
    dataset = os.environ.get("SEED_BQ_DATASET", _DEFAULT_DATASET).strip() or _DEFAULT_DATASET
    return project, dataset


def _load_local_json(filename: str) -> list[dict[str, Any]]:
    path = _DATA_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


def lookup_coffee_menu(category: str = "all") -> str:
    """Query the Pancras Square Roastery drink and pastry menu from BigQuery.

    Args:
        category: Optional category filter such as 'espresso', 'filter', 'cold', 'tea', 'pastry', or 'all'.

    Returns:
        JSON string with matching menu items, prices in GBP, caffeine content, and oat milk availability.
    """
    try:
        norm_cat = (category or "all").strip().lower()
        project, dataset = _resolve_project_and_dataset()
        use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}

        if project and not use_offline:
            try:
                from google.cloud import bigquery

                client = bigquery.Client(project=project)
                table_ref = f"`{project}.{dataset}.menu`"
                if norm_cat and norm_cat != "all":
                    query = (
                        f"SELECT item_id, name, category, price_gbp, caffeine_mg, "
                        f"oat_milk_available, in_stock FROM {table_ref} "
                        f"WHERE LOWER(category) = @category ORDER BY price_gbp ASC"
                    )
                    job_config = bigquery.QueryJobConfig(
                        query_parameters=[
                            bigquery.ScalarQueryParameter("category", "STRING", norm_cat)
                        ]
                    )
                else:
                    query = (
                        f"SELECT item_id, name, category, price_gbp, caffeine_mg, "
                        f"oat_milk_available, in_stock FROM {table_ref} "
                        f"ORDER BY category, price_gbp ASC"
                    )
                    job_config = bigquery.QueryJobConfig()

                rows = [dict(row.items()) for row in client.query(query, job_config=job_config).result()]
                return json.dumps({
                    "status": "SUCCESS",
                    "source": f"bigquery:{project}.{dataset}.menu",
                    "category_filter": norm_cat,
                    "count": len(rows),
                    "items": rows,
                })
            except Exception as bq_exc:
                fallback_reason = str(bq_exc)
        else:
            fallback_reason = "GOOGLE_CLOUD_PROJECT unset or SEED_OFFLINE_MODE enabled"

        items = _load_local_json("menu.json")
        if norm_cat and norm_cat != "all":
            items = [i for i in items if str(i.get("category", "")).lower() == norm_cat]
        return json.dumps({
            "status": "SUCCESS",
            "source": "local_seed_json",
            "fallback_reason": fallback_reason,
            "category_filter": norm_cat,
            "count": len(items),
            "items": items,
        })
    except Exception as exc:
        return json.dumps({
            "status": "ERROR",
            "error": str(exc),
        })


def get_roastery_sales_stats(store_location: str = "London Soho") -> str:
    """Query daily café sales metrics, total revenue, and bean stock levels for a store location.

    Args:
        store_location: Store location name (e.g., 'London Soho', 'King\\'s Cross', 'Shoreditch', or 'all').

    Returns:
        JSON string with aggregated revenue in GBP, total cups sold, latest bean stock in kg, and daily breakdown.
    """
    try:
        loc_filter = (store_location or "all").strip()
        project, dataset = _resolve_project_and_dataset()
        use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}

        rows: list[dict[str, Any]] = []
        source = "local_seed_json"
        fallback_reason = "GOOGLE_CLOUD_PROJECT unset or SEED_OFFLINE_MODE enabled"
        if project and not use_offline:
            try:
                from google.cloud import bigquery

                client = bigquery.Client(project=project)
                table_ref = f"`{project}.{dataset}.daily_sales`"
                if loc_filter.lower() != "all":
                    query = (
                        f"SELECT CAST(sale_date AS STRING) AS sale_date, store_location, "
                        f"top_item, cups_sold, revenue_gbp, bean_stock_kg "
                        f"FROM {table_ref} "
                        f"WHERE LOWER(store_location) LIKE LOWER(@loc) "
                        f"ORDER BY sale_date DESC"
                    )
                    job_config = bigquery.QueryJobConfig(
                        query_parameters=[
                            bigquery.ScalarQueryParameter("loc", "STRING", f"%{loc_filter}%")
                        ]
                    )
                else:
                    query = (
                        f"SELECT CAST(sale_date AS STRING) AS sale_date, store_location, "
                        f"top_item, cups_sold, revenue_gbp, bean_stock_kg "
                        f"FROM {table_ref} ORDER BY store_location, sale_date DESC"
                    )
                    job_config = bigquery.QueryJobConfig()

                rows = [dict(row.items()) for row in client.query(query, job_config=job_config).result()]
                source = f"bigquery:{project}.{dataset}.daily_sales"
                fallback_reason = "no matching rows in BigQuery"
            except Exception as bq_exc:
                rows = []
                fallback_reason = str(bq_exc)

        if not rows:
            source = "local_seed_json"
            all_rows = _load_local_json("daily_sales.json")
            if loc_filter.lower() != "all":
                rows = [
                    r for r in all_rows
                    if loc_filter.lower() in str(r.get("store_location", "")).lower()
                ]
            else:
                rows = all_rows

        total_revenue = round(sum(float(r.get("revenue_gbp", 0.0)) for r in rows), 2)
        total_cups = sum(int(r.get("cups_sold", 0)) for r in rows)
        latest_stock_kg = rows[0].get("bean_stock_kg") if rows else None

        return json.dumps({
            "status": "SUCCESS",
            "source": source,
            **({"fallback_reason": fallback_reason} if source == "local_seed_json" else {}),
            "store_location": loc_filter,
            "days_analyzed": len(rows),
            "total_revenue_gbp": total_revenue,
            "total_cups_sold": total_cups,
            "latest_bean_stock_kg": latest_stock_kg,
            "daily_records": rows,
        })
    except Exception as exc:
        return json.dumps({
            "status": "ERROR",
            "error": str(exc),
        })


# Exported tools list per Seed Pack contract.
# Note: submit_bean_reorder is also re-exported here so that when deployed to
# Vertex AI Agent Runtime (where local stdio MCP subprocesses are disabled),
# the agent retains full mock-action parity.
TOOLS = [
    lookup_coffee_menu,
    get_roastery_sales_stats,
    submit_bean_reorder,
]
