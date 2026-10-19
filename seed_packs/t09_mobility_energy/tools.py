"""ADK Function Tools for Seed Pack t09_mobility_energy (BigQuery + Mock Actions)."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from google.cloud import bigquery
from seed_packs.t09_mobility_energy.mcp_server import (
    ACTION_TOOLS,
    authorize_v2g_grid_discharge,
    schedule_smart_charging_plan,
    throttle_depot_transformer_load,
)

_DATA_DIR = Path(__file__).resolve().parent / "data"
_DEFAULT_DATASET = "seed_t09"


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
            "`make seed PACK=t09` to query BigQuery."
        )
    return "SEED_OFFLINE_MODE enabled: rows come from the bundled CSV copy."


def _bq_error_hint(exc: Exception) -> str:
    """Turn a BigQuery failure into an actionable fallback reason."""
    return (
        f"BigQuery query failed ({type(exc).__name__}: {exc}). These rows come from the "
        "bundled CSV copy. If the dataset is missing run `make seed PACK=t09`; if "
        "credentials are missing run `gcloud auth application-default login`."
    )


def _read_local_csv(name: str) -> list[dict[str, Any]]:
    path = _DATA_DIR / f"{name}.csv"
    with path.open("r", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def query_fleet_charging_needs(
    depot_id: str = "DEP-MADRID-SOUTH",
    max_soc_pct: int = 60,
) -> str:
    """Query plugged-in EVs at a depot with battery SoC at or below max_soc_pct in BigQuery.

    Args:
        depot_id: Depot ID (e.g. 'DEP-MADRID-SOUTH', 'DEP-LONDON-EAST', or 'all').
        max_soc_pct: Maximum current battery SoC percentage filter (default 60).

    Returns:
        JSON string with vehicles requiring charging sorted by lowest battery SoC first.
    """
    project, dataset = _resolve_project_and_dataset()
    dep_clean = (depot_id or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.ev_fleet_telemetry`"
            clauses = ["battery_soc_pct <= @max_soc"]
            params: list[Any] = [bigquery.ScalarQueryParameter("max_soc", "INT64", int(max_soc_pct))]
            if dep_clean.lower() != "all":
                clauses.append("UPPER(depot_id) = UPPER(@dep)")
                params.append(bigquery.ScalarQueryParameter("dep", "STRING", dep_clean))
            where_sql = " AND ".join(clauses)
            sql = (
                f"SELECT vehicle_id, depot_id, vehicle_type, battery_soc_pct, target_soc_pct, "
                f"next_route_departure_hour, next_route_km, v2g_capable, plug_status "
                f"FROM {table_ref} WHERE {where_sql} ORDER BY battery_soc_pct ASC LIMIT 15"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.ev_fleet_telemetry",
                "count": len(rows),
                "vehicles": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("ev_fleet_telemetry")
        if int(r["battery_soc_pct"]) <= int(max_soc_pct)
        and (dep_clean.lower() == "all" or r["depot_id"].upper() == dep_clean.upper())
    ]
    rows.sort(key=lambda r: int(r["battery_soc_pct"]))
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows[:15]),
        "vehicles": rows[:15],
    })


def get_grid_tariff_forecast(
    depot_id: str = "DEP-MADRID-SOUTH",
    tariff_tier: str = "all",
) -> str:
    """Query grid tariff windows, MWh pricing, carbon intensity, and V2G export bonuses from BigQuery.

    Args:
        depot_id: Depot ID (e.g. 'DEP-MADRID-SOUTH', 'DEP-LONDON-EAST', or 'all').
        tariff_tier: Tariff tier filter ('SUPER_VALLEY_SOLAR_WIND', 'SHOULDER', 'PEAK_SURGE', or 'all').

    Returns:
        JSON string with grid tariff windows ordered by price EUR/MWh ascending.
    """
    project, dataset = _resolve_project_and_dataset()
    dep_clean = (depot_id or "all").strip()
    tier_clean = (tariff_tier or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.grid_tariff_windows`"
            clauses: list[str] = []
            params: list[Any] = []
            if dep_clean.lower() != "all":
                clauses.append("UPPER(depot_id) = UPPER(@dep)")
                params.append(bigquery.ScalarQueryParameter("dep", "STRING", dep_clean))
            if tier_clean.lower() != "all":
                clauses.append("UPPER(tariff_tier) = UPPER(@tier)")
                params.append(bigquery.ScalarQueryParameter("tier", "STRING", tier_clean))
            where_sql = f"WHERE {' AND '.join(clauses)} " if clauses else ""
            sql = (
                f"SELECT window_id, grid_zone, depot_id, hour_utc, tariff_tier, "
                f"price_eur_per_mwh, carbon_intensity_g_co2_kwh, v2g_export_bonus_eur_mwh, grid_operator_notice "
                f"FROM {table_ref} {where_sql}ORDER BY price_eur_per_mwh ASC LIMIT 15"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.grid_tariff_windows",
                "count": len(rows),
                "tariff_windows": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("grid_tariff_windows")
        if (dep_clean.lower() == "all" or r["depot_id"].upper() == dep_clean.upper())
        and (tier_clean.lower() == "all" or r["tariff_tier"].upper() == tier_clean.upper())
    ]
    rows.sort(key=lambda r: float(r["price_eur_per_mwh"]))
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows[:15]),
        "tariff_windows": rows[:15],
    })


def inspect_depot_charger_headroom(depot_id: str = "DEP-MADRID-SOUTH") -> str:
    """Inspect charger bay capacity, transformer headroom kW, and thermal status at a depot in BigQuery.

    Args:
        depot_id: Depot ID (e.g. 'DEP-MADRID-SOUTH', 'DEP-LONDON-EAST').

    Returns:
        JSON string with charger bay capacity and transformer headroom.
    """
    project, dataset = _resolve_project_and_dataset()
    dep_clean = (depot_id or "DEP-MADRID-SOUTH").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.depot_charger_capacity`"
            sql = (
                f"SELECT charger_bay_id, depot_id, max_power_kw, transformer_headroom_kw, "
                f"active_load_kw, operational_status "
                f"FROM {table_ref} WHERE UPPER(depot_id) = UPPER(@dep) "
                f"ORDER BY transformer_headroom_kw DESC LIMIT 15"
            )
            cfg = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("dep", "STRING", dep_clean)]
            )
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.depot_charger_capacity",
                "count": len(rows),
                "charger_bays": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("depot_charger_capacity")
        if r["depot_id"].upper() == dep_clean.upper()
    ][:15]
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows),
        "charger_bays": rows,
    })


TOOLS = [
    query_fleet_charging_needs,
    get_grid_tariff_forecast,
    inspect_depot_charger_headroom,
]

__all__ = [
    "TOOLS",
    "ACTION_TOOLS",
    "query_fleet_charging_needs",
    "get_grid_tariff_forecast",
    "inspect_depot_charger_headroom",
    "schedule_smart_charging_plan",
    "authorize_v2g_grid_discharge",
    "throttle_depot_transformer_load",
]
