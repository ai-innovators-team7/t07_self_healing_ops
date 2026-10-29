"""ADK Function Tools for Seed Pack t03_catalog_discovery (BigQuery + Mock Actions)."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from google.cloud import bigquery
from seed_packs.t03_catalog_discovery.mcp_server import (
    ACTION_TOOLS,
    attach_protection_quote,
    create_curated_shortlist,
    flag_suspect_listing,
)

_DATA_DIR = Path(__file__).resolve().parent / "data"
_DEFAULT_DATASET = "seed_t03"


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
            "`make seed PACK=t03` to query BigQuery."
        )
    return "SEED_OFFLINE_MODE enabled: rows come from the bundled CSV copy."


def _bq_error_hint(exc: Exception) -> str:
    """Turn a BigQuery failure into an actionable fallback reason."""
    return (
        f"BigQuery query failed ({type(exc).__name__}: {exc}). These rows come from the "
        "bundled CSV copy. If the dataset is missing run `make seed PACK=t03`; if "
        "credentials are missing run `gcloud auth application-default login`."
    )


def _read_local_csv(name: str) -> list[dict[str, Any]]:
    path = _DATA_DIR / f"{name}.csv"
    with path.open("r", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def search_marketplace_listings(
    category: str = "Refurbished_EBikes",
    max_price_eur: float = 1500.0,
    condition: str = "all",
    limit: int = 10,
) -> str:
    """Search verified secondhand marketplace listings in BigQuery by category, max price, and condition.

    Args:
        category: Listing category (e.g. 'Refurbished_EBikes', 'Mirrorless_Cameras', or 'all').
        max_price_eur: Maximum buyer budget in EUR (default 1500.0).
        condition: Condition filter ('Like_New', 'Refurbished_Grade_A', 'Good_Used', or 'all').
        limit: Max listings to return (default 10).

    Returns:
        JSON string with matching listings ordered by seller rating descending.
    """
    project, dataset = _resolve_project_and_dataset()
    cat_clean = (category or "all").strip()
    cond_clean = (condition or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.marketplace_listings`"
            clauses = ["price_eur <= @max_price"]
            params: list[Any] = [
                bigquery.ScalarQueryParameter("max_price", "FLOAT64", float(max_price_eur)),
                bigquery.ScalarQueryParameter("lim", "INT64", int(limit)),
            ]
            if cat_clean.lower() != "all":
                clauses.append("LOWER(category) = LOWER(@cat)")
                params.append(bigquery.ScalarQueryParameter("cat", "STRING", cat_clean))
            if cond_clean.lower() != "all":
                clauses.append("LOWER(condition) = LOWER(@cond)")
                params.append(bigquery.ScalarQueryParameter("cond", "STRING", cond_clean))
            where_sql = " AND ".join(clauses)
            sql = (
                f"SELECT listing_id, title, category, condition, price_eur, seller_rating, "
                f"city, warranty_eligible, attributes_json, description "
                f"FROM {table_ref} WHERE {where_sql} "
                f"ORDER BY seller_rating DESC, price_eur ASC LIMIT @lim"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.marketplace_listings",
                "count": len(rows),
                "listings": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("marketplace_listings")
        if float(r["price_eur"]) <= float(max_price_eur)
        and (cat_clean.lower() == "all" or r["category"].lower() == cat_clean.lower())
        and (cond_clean.lower() == "all" or r["condition"].lower() == cond_clean.lower())
    ]
    rows.sort(key=lambda r: float(r["seller_rating"]), reverse=True)
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows[: int(limit)]),
        "listings": rows[: int(limit)],
    })


def get_compatible_protection_plans(
    category: str = "Refurbished_EBikes",
    item_price_eur: float = 900.0,
) -> str:
    """Query protection plans in BigQuery that cover the given category and item price.

    Args:
        category: Marketplace category (e.g. 'Refurbished_EBikes', 'Mirrorless_Cameras').
        item_price_eur: Price of the item in EUR to check against max_coverage_eur.

    Returns:
        JSON string with compatible protection plans sorted by monthly fee.
    """
    project, dataset = _resolve_project_and_dataset()
    cat_clean = category.strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.protection_plans`"
            sql = (
                f"SELECT plan_id, category, plan_tier, monthly_fee_eur, max_coverage_eur, "
                f"deductible_eur, covered_perils FROM {table_ref} "
                f"WHERE LOWER(category) = LOWER(@cat) AND max_coverage_eur >= @price "
                f"ORDER BY monthly_fee_eur ASC LIMIT 10"
            )
            cfg = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("cat", "STRING", cat_clean),
                    bigquery.ScalarQueryParameter("price", "FLOAT64", float(item_price_eur)),
                ]
            )
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.protection_plans",
                "count": len(rows),
                "plans": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("protection_plans")
        if r["category"].lower() == cat_clean.lower()
        and float(r["max_coverage_eur"]) >= float(item_price_eur)
    ]
    rows.sort(key=lambda r: float(r["monthly_fee_eur"]))
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows[:10]),
        "plans": rows[:10],
    })


def analyze_search_dropoffs(category: str = "all") -> str:
    """Aggregate buyer search session drop-off reasons by category in BigQuery.

    Args:
        category: Optional category filter (e.g. 'Refurbished_EBikes' or 'all').

    Returns:
        JSON string with session counts grouped by dropoff_reason.
    """
    project, dataset = _resolve_project_and_dataset()
    cat_clean = (category or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.search_sessions`"
            where_sql = ""
            params: list[Any] = []
            if cat_clean.lower() != "all":
                where_sql = "WHERE LOWER(matched_category) = LOWER(@cat) "
                params.append(bigquery.ScalarQueryParameter("cat", "STRING", cat_clean))
            sql = (
                f"SELECT matched_category, dropoff_reason, COUNT(*) AS session_count "
                f"FROM {table_ref} {where_sql}"
                f"GROUP BY matched_category, dropoff_reason ORDER BY session_count DESC"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.search_sessions",
                "dropoff_summary": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    raw = _read_local_csv("search_sessions")
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "total_sessions": len(raw),
    })


TOOLS = [
    search_marketplace_listings,
    get_compatible_protection_plans,
    analyze_search_dropoffs,
]

__all__ = [
    "TOOLS",
    "ACTION_TOOLS",
    "search_marketplace_listings",
    "get_compatible_protection_plans",
    "analyze_search_dropoffs",
    "create_curated_shortlist",
    "attach_protection_quote",
    "flag_suspect_listing",
]
