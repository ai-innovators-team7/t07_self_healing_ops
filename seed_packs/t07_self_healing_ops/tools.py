"""ADK Function Tools for Seed Pack t07_self_healing_ops (BigQuery + Mock Actions)."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from google.cloud import bigquery
from seed_packs.t07_self_healing_ops.mcp_server import (
    ACTION_TOOLS,
    annotate_incident_timeline,
    execute_canary_rollback,
    scale_service_replicas,
)

_DATA_DIR = Path(__file__).resolve().parent / "data"
_DEFAULT_DATASET = "seed_t07"


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
            "`make seed PACK=t07` to query BigQuery."
        )
    return "SEED_OFFLINE_MODE enabled: rows come from the bundled CSV copy."


def _bq_error_hint(exc: Exception) -> str:
    """Turn a BigQuery failure into an actionable fallback reason."""
    return (
        f"BigQuery query failed ({type(exc).__name__}: {exc}). These rows come from the "
        "bundled CSV copy. If the dataset is missing run `make seed PACK=t07`; if "
        "credentials are missing run `gcloud auth application-default login`."
    )


def _read_local_csv(name: str) -> list[dict[str, Any]]:
    path = _DATA_DIR / f"{name}.csv"
    with path.open("r", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def query_active_incidents(
    severity: str = "SEV1",
    service_name: str = "all",
) -> str:
    """Query active (OPEN) production service incidents in BigQuery by severity and service name.

    Args:
        severity: Incident severity ('SEV1', 'SEV2', 'SEV3', or 'all').
        service_name: Microservice name (e.g. 'checkout-payment-svc', 'auth-token-gateway', or 'all').

    Returns:
        JSON string with open service incidents sorted by error rate descending.
    """
    project, dataset = _resolve_project_and_dataset()
    sev_clean = (severity or "all").strip()
    svc_clean = (service_name or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.service_incidents`"
            clauses = ["status = 'OPEN'"]
            params: list[Any] = []
            if sev_clean.lower() != "all":
                clauses.append("UPPER(severity) = UPPER(@sev)")
                params.append(bigquery.ScalarQueryParameter("sev", "STRING", sev_clean))
            if svc_clean.lower() != "all":
                clauses.append("LOWER(service_name) = LOWER(@svc)")
                params.append(bigquery.ScalarQueryParameter("svc", "STRING", svc_clean))
            where_sql = " AND ".join(clauses)
            sql = (
                f"SELECT incident_id, service_name, cluster_region, severity, symptom_code, "
                f"error_rate_pct, p99_latency_ms, active_release_id, status, recent_log_snippet "
                f"FROM {table_ref} WHERE {where_sql} ORDER BY error_rate_pct DESC LIMIT 15"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.service_incidents",
                "count": len(rows),
                "incidents": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("service_incidents")
        if r["status"] == "OPEN"
        and (sev_clean.lower() == "all" or r["severity"].lower() == sev_clean.lower())
        and (svc_clean.lower() == "all" or r["service_name"].lower() == svc_clean.lower())
    ]
    rows.sort(key=lambda r: float(r["error_rate_pct"]), reverse=True)
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows[:15]),
        "incidents": rows[:15],
    })


def inspect_deployment_release(release_id: str = "REL-0001") -> str:
    """Inspect deployment release metadata, previous stable version, and canary pass rate in BigQuery.

    Args:
        release_id: Deployment release ID (e.g. 'REL-0001' or 'REL-0019').

    Returns:
        JSON string with release details and rollback safety flag.
    """
    project, dataset = _resolve_project_and_dataset()
    rel_clean = (release_id or "REL-0001").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.deployment_releases`"
            sql = (
                f"SELECT release_id, service_name, version_tag, previous_stable_version, "
                f"deployed_at, author_team, change_type, canary_pass_rate_pct, rollback_safe "
                f"FROM {table_ref} WHERE UPPER(release_id) = UPPER(@rel) LIMIT 5"
            )
            cfg = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("rel", "STRING", rel_clean)]
            )
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.deployment_releases",
                "count": len(rows),
                "releases": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("deployment_releases")
        if r["release_id"].upper() == rel_clean.upper()
    ][:5]
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows),
        "releases": rows,
    })


def lookup_slo_runbook(
    service_name: str = "checkout-payment-svc",
    symptom_code: str = "all",
) -> str:
    """Look up the SRE SLO runbook, recommended action, and safe replica bounds from BigQuery.

    Args:
        service_name: Microservice name (e.g. 'checkout-payment-svc', 'auth-token-gateway').
        symptom_code: Optional symptom code filter (e.g. 'P99_LATENCY_SPIKE', 'OOM_CRASH_LOOP', or 'all').

    Returns:
        JSON string with matching SRE runbook policies.
    """
    project, dataset = _resolve_project_and_dataset()
    svc_clean = (service_name or "checkout-payment-svc").strip()
    sym_clean = (symptom_code or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.slo_runbooks`"
            clauses = ["LOWER(service_name) = LOWER(@svc)"]
            params: list[Any] = [bigquery.ScalarQueryParameter("svc", "STRING", svc_clean)]
            if sym_clean.lower() != "all":
                clauses.append("UPPER(symptom_code) = UPPER(@sym)")
                params.append(bigquery.ScalarQueryParameter("sym", "STRING", sym_clean))
            where_sql = " AND ".join(clauses)
            sql = (
                f"SELECT runbook_id, service_name, symptom_code, slo_target_pct, "
                f"error_budget_burn_rate, recommended_action, min_safe_replicas, max_safe_replicas "
                f"FROM {table_ref} WHERE {where_sql} ORDER BY error_budget_burn_rate DESC LIMIT 10"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.slo_runbooks",
                "count": len(rows),
                "runbooks": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("slo_runbooks")
        if r["service_name"].lower() == svc_clean.lower()
        and (sym_clean.lower() == "all" or r["symptom_code"].lower() == sym_clean.lower())
    ][:10]
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows),
        "runbooks": rows,
    })


TOOLS = [
    query_active_incidents,
    inspect_deployment_release,
    lookup_slo_runbook,
]

__all__ = [
    "TOOLS",
    "ACTION_TOOLS",
    "query_active_incidents",
    "inspect_deployment_release",
    "lookup_slo_runbook",
    "execute_canary_rollback",
    "scale_service_replicas",
    "annotate_incident_timeline",
]
