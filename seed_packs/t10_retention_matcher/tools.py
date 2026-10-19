"""ADK Function Tools for Seed Pack t10_retention_matcher (BigQuery + Mock Actions)."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from google.cloud import bigquery
from seed_packs.t10_retention_matcher.mcp_server import (
    ACTION_TOOLS,
    dispatch_retention_offer,
    log_churn_prevention_decision,
    schedule_onboarding_rescue_call,
)

_DATA_DIR = Path(__file__).resolve().parent / "data"
_DEFAULT_DATASET = "seed_t10"


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
            "`make seed PACK=t10` to query BigQuery."
        )
    return "SEED_OFFLINE_MODE enabled: rows come from the bundled CSV copy."


def _bq_error_hint(exc: Exception) -> str:
    """Turn a BigQuery failure into an actionable fallback reason."""
    return (
        f"BigQuery query failed ({type(exc).__name__}: {exc}). These rows come from the "
        "bundled CSV copy. If the dataset is missing run `make seed PACK=t10`; if "
        "credentials are missing run `gcloud auth application-default login`."
    )


def _read_local_csv(name: str) -> list[dict[str, Any]]:
    path = _DATA_DIR / f"{name}.csv"
    with path.open("r", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def query_at_risk_subscribers(
    plan_segment: str = "PRO_DESIGN_TEAM",
    min_churn_prob: float = 0.65,
) -> str:
    """Query high-churn-risk subscribers in BigQuery by plan segment and minimum churn probability.

    Args:
        plan_segment: Plan segment ('PRO_DESIGN_TEAM', 'CREATOR_SOLO', 'SMB_COMMERCE_PLUS', 'ENTERPRISE_SEAT_BUNDLE', or 'all').
        min_churn_prob: Minimum churn probability threshold (default 0.65).

    Returns:
        JSON string with at-risk subscribers sorted by LTV EUR descending.
    """
    project, dataset = _resolve_project_and_dataset()
    seg_clean = (plan_segment or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.subscriber_cohorts`"
            clauses = ["churn_probability >= @min_prob"]
            params: list[Any] = [bigquery.ScalarQueryParameter("min_prob", "FLOAT64", float(min_churn_prob))]
            if seg_clean.lower() != "all":
                clauses.append("UPPER(plan_segment) = UPPER(@seg)")
                params.append(bigquery.ScalarQueryParameter("seg", "STRING", seg_clean))
            where_sql = " AND ".join(clauses)
            sql = (
                f"SELECT subscriber_id, account_name, country, plan_segment, tenure_months, "
                f"mrr_eur, ltv_eur, churn_probability, primary_churn_driver, recent_ticket_note "
                f"FROM {table_ref} WHERE {where_sql} ORDER BY ltv_eur DESC LIMIT 15"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.subscriber_cohorts",
                "count": len(rows),
                "subscribers": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("subscriber_cohorts")
        if float(r["churn_probability"]) >= float(min_churn_prob)
        and (seg_clean.lower() == "all" or r["plan_segment"].upper() == seg_clean.upper())
    ]
    rows.sort(key=lambda r: float(r["ltv_eur"]), reverse=True)
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows[:15]),
        "subscribers": rows[:15],
    })


def find_matching_retention_offers(
    churn_driver: str = "PRICE_SENSITIVITY",
    eligible_segment: str = "all",
) -> str:
    """Find catalog retention offers in BigQuery matching a churn driver and plan segment.

    Args:
        churn_driver: Primary churn driver ('PRICE_SENSITIVITY', 'LOW_FEATURE_ADOPTION', 'COMPETITOR_TRIAL', 'SUPPORT_FRICTION', 'SEASONAL_PAUSE').
        eligible_segment: Plan segment filter or 'all'.

    Returns:
        JSON string with eligible retention offers ordered by expected save lift percentage.
    """
    project, dataset = _resolve_project_and_dataset()
    drv_clean = (churn_driver or "PRICE_SENSITIVITY").strip()
    seg_clean = (eligible_segment or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.retention_offer_catalog`"
            clauses = ["UPPER(target_churn_driver) = UPPER(@drv)"]
            params: list[Any] = [bigquery.ScalarQueryParameter("drv", "STRING", drv_clean)]
            if seg_clean.lower() != "all":
                clauses.append("UPPER(eligible_segment) = UPPER(@seg)")
                params.append(bigquery.ScalarQueryParameter("seg", "STRING", seg_clean))
            where_sql = " AND ".join(clauses)
            sql = (
                f"SELECT offer_id, offer_name, target_churn_driver, eligible_segment, "
                f"discount_pct, max_credit_eur, duration_months, expected_save_lift_pct, min_ltv_required_eur "
                f"FROM {table_ref} WHERE {where_sql} ORDER BY expected_save_lift_pct DESC LIMIT 10"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.retention_offer_catalog",
                "count": len(rows),
                "offers": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("retention_offer_catalog")
        if r["target_churn_driver"].upper() == drv_clean.upper()
        and (seg_clean.lower() == "all" or r["eligible_segment"].upper() == seg_clean.upper())
    ]
    rows.sort(key=lambda r: float(r["expected_save_lift_pct"]), reverse=True)
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows[:10]),
        "offers": rows[:10],
    })


def analyze_historical_save_rates(channel: str = "all") -> str:
    """Analyze historical retention intervention outcomes and 90-day retained MRR in BigQuery.

    Args:
        channel: Delivery channel ('IN_APP_MODAL', 'CONCIERGE_EMAIL', 'CSM_CALL', or 'all').

    Returns:
        JSON string with historical intervention outcomes sorted by net MRR retained.
    """
    project, dataset = _resolve_project_and_dataset()
    ch_clean = (channel or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.intervention_outcomes`"
            params: list[Any] = []
            where_sql = ""
            if ch_clean.lower() != "all":
                where_sql = "WHERE UPPER(channel) = UPPER(@ch) "
                params.append(bigquery.ScalarQueryParameter("ch", "STRING", ch_clean))
            sql = (
                f"SELECT outcome_id, subscriber_id, offer_id, channel, accepted, "
                f"retained_90d, net_mrr_retained_eur "
                f"FROM {table_ref} {where_sql}ORDER BY net_mrr_retained_eur DESC LIMIT 15"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.intervention_outcomes",
                "count": len(rows),
                "outcomes": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("intervention_outcomes")
        if ch_clean.lower() == "all" or r["channel"].upper() == ch_clean.upper()
    ]
    rows.sort(key=lambda r: float(r["net_mrr_retained_eur"]), reverse=True)
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows[:15]),
        "outcomes": rows[:15],
    })


TOOLS = [
    query_at_risk_subscribers,
    find_matching_retention_offers,
    analyze_historical_save_rates,
]

__all__ = [
    "TOOLS",
    "ACTION_TOOLS",
    "query_at_risk_subscribers",
    "find_matching_retention_offers",
    "analyze_historical_save_rates",
    "dispatch_retention_offer",
    "schedule_onboarding_rescue_call",
    "log_churn_prevention_decision",
]
