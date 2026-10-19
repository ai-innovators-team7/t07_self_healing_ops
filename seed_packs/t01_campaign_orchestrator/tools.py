"""ADK Function Tools for Seed Pack t01_campaign_orchestrator (BigQuery + Mock Actions)."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from google.cloud import bigquery
from seed_packs.t01_campaign_orchestrator.mcp_server import (
    ACTION_TOOLS,
    create_localized_variant,
    pause_ad_variant,
    place_ad_bid,
)

_DATA_DIR = Path(__file__).resolve().parent / "data"
_DEFAULT_DATASET = "seed_t01"


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
            "`make seed PACK=t01` to query BigQuery."
        )
    return "SEED_OFFLINE_MODE enabled: rows come from the bundled CSV copy."


def _bq_error_hint(exc: Exception) -> str:
    """Turn a BigQuery failure into an actionable fallback reason."""
    return (
        f"BigQuery query failed ({type(exc).__name__}: {exc}). These rows come from the "
        "bundled CSV copy. If the dataset is missing run `make seed PACK=t01`; if "
        "credentials are missing run `gcloud auth application-default login`."
    )


def _read_local_csv(name: str) -> list[dict[str, Any]]:
    path = _DATA_DIR / f"{name}.csv"
    with path.open("r", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def query_underperforming_campaigns(
    city: str = "London",
    max_roas: float = 2.0,
    limit: int = 10,
) -> str:
    """Query ad campaign telemetry in BigQuery for variants with ROAS at or below max_roas.

    Args:
        city: City name filter (e.g. 'London', 'Madrid', 'Barcelona', or 'all').
        max_roas: Maximum ROAS threshold to filter underperforming campaigns (default 2.0).
        limit: Maximum number of rows to return (default 10).

    Returns:
        JSON string listing underperforming campaign telemetry records sorted by lowest ROAS.
    """
    project, dataset = _resolve_project_and_dataset()
    city_clean = (city or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.campaign_telemetry`"
            params: list[Any] = [
                bigquery.ScalarQueryParameter("max_roas", "FLOAT64", float(max_roas)),
                bigquery.ScalarQueryParameter("lim", "INT64", int(limit)),
            ]
            where_city = ""
            if city_clean.lower() != "all":
                where_city = "AND LOWER(city) = LOWER(@city) "
                params.append(bigquery.ScalarQueryParameter("city", "STRING", city_clean))
            sql = (
                f"SELECT telemetry_id, variant_id, event_id, channel, city, impressions, "
                f"clicks, conversions, spend_eur, revenue_eur, roas, current_cpm_bid_eur "
                f"FROM {table_ref} WHERE roas <= @max_roas {where_city}"
                f"ORDER BY roas ASC, spend_eur DESC LIMIT @lim"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.campaign_telemetry",
                "city_filter": city_clean,
                "max_roas": max_roas,
                "count": len(rows),
                "campaigns": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = _read_local_csv("campaign_telemetry")
    filtered = [
        r for r in rows
        if float(r["roas"]) <= float(max_roas)
        and (city_clean.lower() == "all" or r["city"].lower() == city_clean.lower())
    ]
    filtered.sort(key=lambda r: float(r["roas"]))
    sliced = filtered[: int(limit)]
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(sliced),
        "campaigns": sliced,
    })


def get_event_ad_variants(event_id: str = "EVT-0001") -> str:
    """Retrieve event details and all associated localized ad variants from BigQuery.

    Args:
        event_id: Event ID to inspect (e.g. 'EVT-0001', 'EVT-0013').

    Returns:
        JSON string containing event metadata and its ad variants across channels and locales.
    """
    project, dataset = _resolve_project_and_dataset()
    evt_clean = event_id.strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            evt_sql = (
                f"SELECT event_id, event_name, city, country, category, venue, "
                f"CAST(event_date AS STRING) AS event_date, ticket_price_eur, "
                f"target_audience, available_tickets "
                f"FROM `{project}.{dataset}.events_catalog` WHERE event_id = @eid"
            )
            var_sql = (
                f"SELECT variant_id, event_id, channel, locale, headline, visual_prompt, "
                f"cta_text, compliance_status, production_cost_eur "
                f"FROM `{project}.{dataset}.ad_variants` WHERE event_id = @eid "
                f"ORDER BY variant_id"
            )
            cfg = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("eid", "STRING", evt_clean)]
            )
            events = [dict(r.items()) for r in client.query(evt_sql, job_config=cfg).result()]
            variants = [dict(r.items()) for r in client.query(var_sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}",
                "event": events[0] if events else None,
                "variants_count": len(variants),
                "variants": variants,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    events = [r for r in _read_local_csv("events_catalog") if r["event_id"] == evt_clean]
    variants = [r for r in _read_local_csv("ad_variants") if r["event_id"] == evt_clean]
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "event": events[0] if events else None,
        "variants_count": len(variants),
        "variants": variants,
    })


def get_channel_roi_summary(channel: str = "all") -> str:
    """Aggregate spend, revenue, conversions, and average ROAS by ad channel in BigQuery.

    Args:
        channel: Optional channel filter (e.g. 'Meta_Reels', 'TikTok_Pulse', or 'all').

    Returns:
        JSON string summarizing total spend, revenue, conversions, and average ROAS per channel.
    """
    project, dataset = _resolve_project_and_dataset()
    ch_clean = (channel or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.campaign_telemetry`"
            where_clause = ""
            params: list[Any] = []
            if ch_clean.lower() != "all":
                where_clause = "WHERE LOWER(channel) = LOWER(@ch) "
                params.append(bigquery.ScalarQueryParameter("ch", "STRING", ch_clean))
            sql = (
                f"SELECT channel, COUNT(*) AS records, "
                f"ROUND(SUM(spend_eur), 2) AS total_spend_eur, "
                f"ROUND(SUM(revenue_eur), 2) AS total_revenue_eur, "
                f"SUM(conversions) AS total_conversions, "
                f"ROUND(AVG(roas), 2) AS avg_roas "
                f"FROM {table_ref} {where_clause}"
                f"GROUP BY channel ORDER BY avg_roas DESC"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.campaign_telemetry",
                "channels": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    raw = _read_local_csv("campaign_telemetry")
    if ch_clean.lower() != "all":
        raw = [r for r in raw if r["channel"].lower() == ch_clean.lower()]
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "records_analyzed": len(raw),
    })


TOOLS = [
    query_underperforming_campaigns,
    get_event_ad_variants,
    get_channel_roi_summary,
]

__all__ = [
    "TOOLS",
    "ACTION_TOOLS",
    "query_underperforming_campaigns",
    "get_event_ad_variants",
    "get_channel_roi_summary",
    "place_ad_bid",
    "create_localized_variant",
    "pause_ad_variant",
]
