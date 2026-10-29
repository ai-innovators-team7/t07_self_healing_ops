"""ADK Function Tools for Seed Pack t08_travel_concierge (BigQuery + Mock Actions)."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from google.cloud import bigquery
from seed_packs.t08_travel_concierge.mcp_server import (
    ACTION_TOOLS,
    issue_compensation_voucher,
    rebook_passenger_segment,
    sync_hotel_late_checkin,
)

_DATA_DIR = Path(__file__).resolve().parent / "data"
_DEFAULT_DATASET = "seed_t08"


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
            "`make seed PACK=t08` to query BigQuery."
        )
    return "SEED_OFFLINE_MODE enabled: rows come from the bundled CSV copy."


def _bq_error_hint(exc: Exception) -> str:
    """Turn a BigQuery failure into an actionable fallback reason."""
    return (
        f"BigQuery query failed ({type(exc).__name__}: {exc}). These rows come from the "
        "bundled CSV copy. If the dataset is missing run `make seed PACK=t08`; if "
        "credentials are missing run `gcloud auth application-default login`."
    )


def _read_local_csv(name: str) -> list[dict[str, Any]]:
    path = _DATA_DIR / f"{name}.csv"
    with path.open("r", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def query_disrupted_passengers(
    origin_airport: str = "MAD",
    loyalty_tier: str = "all",
) -> str:
    """Query unresolved disrupted passenger itineraries in BigQuery by origin airport and loyalty tier.

    Args:
        origin_airport: IATA airport code (e.g. 'MAD', 'BCN', 'LHR', or 'all').
        loyalty_tier: Loyalty tier filter ('DIAMOND_VIP', 'GOLD_ELITE', 'SILVER_PLUS', 'STANDARD', or 'all').

    Returns:
        JSON string with disrupted passenger itineraries sorted by delay minutes descending.
    """
    project, dataset = _resolve_project_and_dataset()
    orig_clean = (origin_airport or "all").strip()
    tier_clean = (loyalty_tier or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.disrupted_itineraries`"
            clauses = ["recovery_status = 'UNRESOLVED'"]
            params: list[Any] = []
            if orig_clean.lower() != "all":
                clauses.append("UPPER(origin_airport) = UPPER(@orig)")
                params.append(bigquery.ScalarQueryParameter("orig", "STRING", orig_clean))
            if tier_clean.lower() != "all":
                clauses.append("UPPER(loyalty_tier) = UPPER(@tier)")
                params.append(bigquery.ScalarQueryParameter("tier", "STRING", tier_clean))
            where_sql = " AND ".join(clauses)
            sql = (
                f"SELECT itinerary_id, passenger_name, loyalty_tier, origin_airport, destination_airport, "
                f"disrupted_flight, disruption_type, delay_minutes, hotel_booking_id, recovery_status "
                f"FROM {table_ref} WHERE {where_sql} ORDER BY delay_minutes DESC LIMIT 15"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.disrupted_itineraries",
                "count": len(rows),
                "itineraries": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("disrupted_itineraries")
        if r["recovery_status"] == "UNRESOLVED"
        and (orig_clean.lower() == "all" or r["origin_airport"].upper() == orig_clean.upper())
        and (tier_clean.lower() == "all" or r["loyalty_tier"].upper() == tier_clean.upper())
    ]
    rows.sort(key=lambda r: int(r["delay_minutes"]), reverse=True)
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows[:15]),
        "itineraries": rows[:15],
    })


def search_rebooking_options(
    origin_airport: str = "MAD",
    destination_airport: str = "LHR",
) -> str:
    """Search available replacement flight and high-speed rail seats in BigQuery.

    Args:
        origin_airport: Origin IATA code (e.g. 'MAD', 'BCN', 'LHR').
        destination_airport: Destination IATA code (e.g. 'LHR', 'MAD', 'BCN').

    Returns:
        JSON string with available rebooking options ordered by departure time.
    """
    project, dataset = _resolve_project_and_dataset()
    orig_clean = (origin_airport or "MAD").strip()
    dest_clean = (destination_airport or "LHR").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.rebooking_inventory`"
            sql = (
                f"SELECT option_id, origin_airport, destination_airport, carrier_mode, "
                f"departure_time, cabin_class, seats_available, fare_diff_eur, eu261_eligible "
                f"FROM {table_ref} "
                f"WHERE UPPER(origin_airport) = UPPER(@orig) AND UPPER(destination_airport) = UPPER(@dest) "
                f"AND seats_available > 0 ORDER BY departure_time ASC LIMIT 10"
            )
            cfg = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("orig", "STRING", orig_clean),
                    bigquery.ScalarQueryParameter("dest", "STRING", dest_clean),
                ]
            )
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.rebooking_inventory",
                "count": len(rows),
                "options": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("rebooking_inventory")
        if r["origin_airport"].upper() == orig_clean.upper()
        and r["destination_airport"].upper() == dest_clean.upper()
        and int(r["seats_available"]) > 0
    ][:10]
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows),
        "options": rows,
    })


def find_partner_hotels(airport_code: str = "MAD") -> str:
    """Find contracted IROPS partner hotels with available rooms near an airport in BigQuery.

    Args:
        airport_code: IATA airport code (e.g. 'MAD', 'BCN', 'LHR').

    Returns:
        JSON string with partner hotels and contracted rates.
    """
    project, dataset = _resolve_project_and_dataset()
    ap_clean = (airport_code or "MAD").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.partner_hotels`"
            sql = (
                f"SELECT hotel_id, airport_code, property_name, rooms_available, "
                f"contracted_rate_eur, shuttle_included, late_checkin_guaranteed, supplier_feed_note "
                f"FROM {table_ref} WHERE UPPER(airport_code) = UPPER(@ap) AND rooms_available > 0 "
                f"ORDER BY contracted_rate_eur ASC LIMIT 10"
            )
            cfg = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("ap", "STRING", ap_clean)]
            )
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.partner_hotels",
                "count": len(rows),
                "hotels": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("partner_hotels")
        if r["airport_code"].upper() == ap_clean.upper() and int(r["rooms_available"]) > 0
    ]
    rows.sort(key=lambda r: float(r["contracted_rate_eur"]))
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows[:10]),
        "hotels": rows[:10],
    })


TOOLS = [
    query_disrupted_passengers,
    search_rebooking_options,
    find_partner_hotels,
]

__all__ = [
    "TOOLS",
    "ACTION_TOOLS",
    "query_disrupted_passengers",
    "search_rebooking_options",
    "find_partner_hotels",
    "rebook_passenger_segment",
    "sync_hotel_late_checkin",
    "issue_compensation_voucher",
]
