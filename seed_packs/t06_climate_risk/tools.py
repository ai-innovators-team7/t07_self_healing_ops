"""ADK Function Tools for Seed Pack t06_climate_risk (BigQuery + Mock Actions)."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from google.cloud import bigquery
from seed_packs.t06_climate_risk.mcp_server import (
    ACTION_TOOLS,
    issue_renewal_quote_adjustment,
    register_catastrophe_accumulation_alert,
    trigger_loss_prevention_inspection,
)

_DATA_DIR = Path(__file__).resolve().parent / "data"
_DEFAULT_DATASET = "seed_t06"


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
            "`make seed PACK=t06` to query BigQuery."
        )
    return "SEED_OFFLINE_MODE enabled: rows come from the bundled CSV copy."


def _bq_error_hint(exc: Exception) -> str:
    """Turn a BigQuery failure into an actionable fallback reason."""
    return (
        f"BigQuery query failed ({type(exc).__name__}: {exc}). These rows come from the "
        "bundled CSV copy. If the dataset is missing run `make seed PACK=t06`; if "
        "credentials are missing run `gcloud auth application-default login`."
    )


def _read_local_csv(name: str) -> list[dict[str, Any]]:
    path = _DATA_DIR / f"{name}.csv"
    with path.open("r", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def query_exposed_assets(
    region: str = "ES_Valencia_Coast",
    min_insured_value_eur: float = 2000000.0,
) -> str:
    """Query insured commercial assets in BigQuery by region and minimum insured value.

    Args:
        region: Geographic region (e.g. 'ES_Valencia_Coast', 'ES_Andalucia_Inland', 'UK_Thames_Valley', or 'all').
        min_insured_value_eur: Minimum insured value in EUR (default 2,000,000).

    Returns:
        JSON string with matching insured assets sorted by insured value descending.
    """
    project, dataset = _resolve_project_and_dataset()
    reg_clean = (region or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.insured_assets`"
            clauses = ["insured_value_eur >= @min_val"]
            params: list[Any] = [bigquery.ScalarQueryParameter("min_val", "FLOAT64", float(min_insured_value_eur))]
            if reg_clean.lower() != "all":
                clauses.append("LOWER(region) = LOWER(@reg)")
                params.append(bigquery.ScalarQueryParameter("reg", "STRING", reg_clean))
            where_sql = " AND ".join(clauses)
            sql = (
                f"SELECT asset_id, policyholder_name, region, asset_type, latitude, longitude, "
                f"insured_value_eur, current_deductible_eur, mitigation_status, broker_submission_note "
                f"FROM {table_ref} WHERE {where_sql} ORDER BY insured_value_eur DESC LIMIT 15"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.insured_assets",
                "count": len(rows),
                "assets": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("insured_assets")
        if float(r["insured_value_eur"]) >= float(min_insured_value_eur)
        and (reg_clean.lower() == "all" or r["region"].lower() == reg_clean.lower())
    ]
    rows.sort(key=lambda r: float(r["insured_value_eur"]), reverse=True)
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows[:15]),
        "assets": rows[:15],
    })


def get_climate_hazard_projections(
    region: str = "ES_Valencia_Coast",
    hazard_type: str = "all",
) -> str:
    """Query climate hazard grid projections (intensity score, exceedance probability, loss multiplier) from BigQuery.

    Args:
        region: Geographic region (e.g. 'ES_Valencia_Coast', 'DE_Rhine_Basin', or 'all').
        hazard_type: Hazard filter (e.g. 'Flash_Flood', 'Extreme_Heatwave', 'Coastal_Storm_Surge', or 'all').

    Returns:
        JSON string with climate hazard grid projections ordered by hazard intensity score.
    """
    project, dataset = _resolve_project_and_dataset()
    reg_clean = (region or "all").strip()
    haz_clean = (hazard_type or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.climate_hazard_grids`"
            clauses: list[str] = []
            params: list[Any] = []
            if reg_clean.lower() != "all":
                clauses.append("LOWER(region) = LOWER(@reg)")
                params.append(bigquery.ScalarQueryParameter("reg", "STRING", reg_clean))
            if haz_clean.lower() != "all":
                clauses.append("LOWER(hazard_type) = LOWER(@haz)")
                params.append(bigquery.ScalarQueryParameter("haz", "STRING", haz_clean))
            where_sql = f"WHERE {' AND '.join(clauses)} " if clauses else ""
            sql = (
                f"SELECT grid_id, region, hazard_type, scenario_horizon, return_period_years, "
                f"hazard_intensity_score, annual_exceedance_prob, projected_loss_multiplier "
                f"FROM {table_ref} {where_sql}ORDER BY hazard_intensity_score DESC LIMIT 15"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.climate_hazard_grids",
                "count": len(rows),
                "hazard_grids": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("climate_hazard_grids")
        if (reg_clean.lower() == "all" or r["region"].lower() == reg_clean.lower())
        and (haz_clean.lower() == "all" or r["hazard_type"].lower() == haz_clean.lower())
    ]
    rows.sort(key=lambda r: float(r["hazard_intensity_score"]), reverse=True)
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows[:15]),
        "hazard_grids": rows[:15],
    })


def summarize_historical_claims(region: str = "all") -> str:
    """Summarize historical weather loss claims and downtime days by region and hazard type from BigQuery.

    Args:
        region: Geographic region filter (e.g. 'ES_Valencia_Coast' or 'all').

    Returns:
        JSON string with historical claim records sorted by gross loss EUR descending.
    """
    project, dataset = _resolve_project_and_dataset()
    reg_clean = (region or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.historical_loss_claims`"
            params: list[Any] = []
            where_sql = ""
            if reg_clean.lower() != "all":
                where_sql = "WHERE LOWER(region) = LOWER(@reg) "
                params.append(bigquery.ScalarQueryParameter("reg", "STRING", reg_clean))
            sql = (
                f"SELECT claim_id, asset_id, region, event_date, hazard_type, "
                f"gross_loss_eur, payout_eur, downtime_days "
                f"FROM {table_ref} {where_sql}ORDER BY gross_loss_eur DESC LIMIT 15"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.historical_loss_claims",
                "count": len(rows),
                "claims": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("historical_loss_claims")
        if reg_clean.lower() == "all" or r["region"].lower() == reg_clean.lower()
    ]
    rows.sort(key=lambda r: float(r["gross_loss_eur"]), reverse=True)
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows[:15]),
        "claims": rows[:15],
    })


TOOLS = [
    query_exposed_assets,
    get_climate_hazard_projections,
    summarize_historical_claims,
]

__all__ = [
    "TOOLS",
    "ACTION_TOOLS",
    "query_exposed_assets",
    "get_climate_hazard_projections",
    "summarize_historical_claims",
    "issue_renewal_quote_adjustment",
    "trigger_loss_prevention_inspection",
    "register_catastrophe_accumulation_alert",
]
