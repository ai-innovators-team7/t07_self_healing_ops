"""ADK Function Tools for Seed Pack t04_b2b_sourcing (BigQuery + Mock Actions)."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from google.cloud import bigquery
from seed_packs.t04_b2b_sourcing.mcp_server import (
    ACTION_TOOLS,
    issue_purchase_order,
    normalize_supplier_schema,
    quarantine_supplier_feed,
)

_DATA_DIR = Path(__file__).resolve().parent / "data"
_DEFAULT_DATASET = "seed_t04"


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
            "`make seed PACK=t04` to query BigQuery."
        )
    return "SEED_OFFLINE_MODE enabled: rows come from the bundled CSV copy."


def _bq_error_hint(exc: Exception) -> str:
    """Turn a BigQuery failure into an actionable fallback reason."""
    return (
        f"BigQuery query failed ({type(exc).__name__}: {exc}). These rows come from the "
        "bundled CSV copy. If the dataset is missing run `make seed PACK=t04`; if "
        "credentials are missing run `gcloud auth application-default login`."
    )


def _read_local_csv(name: str) -> list[dict[str, Any]]:
    path = _DATA_DIR / f"{name}.csv"
    with path.open("r", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def query_supplier_feeds(
    canonical_category: str = "Industrial_Sensors",
    max_unit_cost_eur: float = 250.0,
    limit: int = 10,
) -> str:
    """Query supplier inventory feeds in BigQuery by canonical category and maximum unit cost.

    Args:
        canonical_category: Canonical category (e.g. 'Industrial_Sensors', 'Lithium_Cells', or 'all').
        max_unit_cost_eur: Maximum unit cost in EUR (default 250.0).
        limit: Max rows to return (default 10).

    Returns:
        JSON string with matching supplier feed rows sorted by lowest unit cost.
    """
    project, dataset = _resolve_project_and_dataset()
    cat_clean = (canonical_category or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.supplier_feeds_raw`"
            params: list[Any] = [
                bigquery.ScalarQueryParameter("max_cost", "FLOAT64", float(max_unit_cost_eur)),
                bigquery.ScalarQueryParameter("lim", "INT64", int(limit)),
            ]
            where_cat = ""
            if cat_clean.lower() != "all":
                where_cat = "AND LOWER(canonical_category) = LOWER(@cat) "
                params.append(bigquery.ScalarQueryParameter("cat", "STRING", cat_clean))
            sql = (
                f"SELECT feed_row_id, supplier_id, external_sku, raw_item_title, "
                f"canonical_category, raw_category_code, unit_cost_eur, moq_units, "
                f"available_units, schema_drift_flag "
                f"FROM {table_ref} WHERE unit_cost_eur <= @max_cost {where_cat}"
                f"ORDER BY unit_cost_eur ASC LIMIT @lim"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.supplier_feeds_raw",
                "count": len(rows),
                "feeds": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("supplier_feeds_raw")
        if float(r["unit_cost_eur"]) <= float(max_unit_cost_eur)
        and (cat_clean.lower() == "all" or r["canonical_category"].lower() == cat_clean.lower())
    ]
    rows.sort(key=lambda r: float(r["unit_cost_eur"]))
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows[: int(limit)]),
        "feeds": rows[: int(limit)],
    })


def get_open_sourcing_rfqs(status: str = "OPEN") -> str:
    """Query sourcing RFQs from BigQuery filtered by status ('OPEN' or 'AWARDED').

    Args:
        status: RFQ status filter ('OPEN', 'AWARDED', or 'all').

    Returns:
        JSON string with matching RFQs including required units and max unit cost.
    """
    project, dataset = _resolve_project_and_dataset()
    st_clean = (status or "OPEN").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.sourcing_rfqs`"
            where_sql = ""
            params: list[Any] = []
            if st_clean.lower() != "all":
                where_sql = "WHERE LOWER(status) = LOWER(@st) "
                params.append(bigquery.ScalarQueryParameter("st", "STRING", st_clean))
            sql = (
                f"SELECT rfq_id, canonical_category, required_units, max_unit_cost_eur, "
                f"target_delivery_days, status, assigned_supplier_id "
                f"FROM {table_ref} {where_sql}ORDER BY rfq_id ASC LIMIT 20"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.sourcing_rfqs",
                "count": len(rows),
                "rfqs": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("sourcing_rfqs")
        if st_clean.lower() == "all" or r["status"].lower() == st_clean.lower()
    ][:20]
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows),
        "rfqs": rows,
    })


def get_supplier_reliability(country: str = "all", min_score: float = 0.75) -> str:
    """Query active B2B suppliers in BigQuery filtered by country and minimum reliability score.

    Args:
        country: ISO country code (e.g. 'ES', 'DE', 'IT', or 'all').
        min_score: Minimum reliability score between 0.0 and 1.0 (default 0.75).

    Returns:
        JSON string listing suppliers ordered by reliability score descending.
    """
    project, dataset = _resolve_project_and_dataset()
    c_clean = (country or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.suppliers`"
            params: list[Any] = [bigquery.ScalarQueryParameter("min_s", "FLOAT64", float(min_score))]
            where_country = ""
            if c_clean.lower() != "all":
                where_country = "AND LOWER(country) = LOWER(@c) "
                params.append(bigquery.ScalarQueryParameter("c", "STRING", c_clean))
            sql = (
                f"SELECT supplier_id, supplier_name, country, tier, reliability_score, "
                f"lead_time_days, api_schema_format, active_status "
                f"FROM {table_ref} WHERE reliability_score >= @min_s {where_country}"
                f"ORDER BY reliability_score DESC LIMIT 20"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.suppliers",
                "count": len(rows),
                "suppliers": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("suppliers")
        if float(r["reliability_score"]) >= float(min_score)
        and (c_clean.lower() == "all" or r["country"].lower() == c_clean.lower())
    ][:20]
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows),
        "suppliers": rows,
    })


TOOLS = [
    query_supplier_feeds,
    get_open_sourcing_rfqs,
    get_supplier_reliability,
]

__all__ = [
    "TOOLS",
    "ACTION_TOOLS",
    "query_supplier_feeds",
    "get_open_sourcing_rfqs",
    "get_supplier_reliability",
    "normalize_supplier_schema",
    "issue_purchase_order",
    "quarantine_supplier_feed",
]
