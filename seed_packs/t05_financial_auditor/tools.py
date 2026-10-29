"""ADK Function Tools for Seed Pack t05_financial_auditor (BigQuery + Mock Actions)."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from google.cloud import bigquery
from seed_packs.t05_financial_auditor.mcp_server import (
    ACTION_TOOLS,
    approve_verified_payout,
    hold_payment_for_audit,
    reconcile_invoice_to_ledger,
)

_DATA_DIR = Path(__file__).resolve().parent / "data"
_DEFAULT_DATASET = "seed_t05"


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
            "`make seed PACK=t05` to query BigQuery."
        )
    return "SEED_OFFLINE_MODE enabled: rows come from the bundled CSV copy."


def _bq_error_hint(exc: Exception) -> str:
    """Turn a BigQuery failure into an actionable fallback reason."""
    return (
        f"BigQuery query failed ({type(exc).__name__}: {exc}). These rows come from the "
        "bundled CSV copy. If the dataset is missing run `make seed PACK=t05`; if "
        "credentials are missing run `gcloud auth application-default login`."
    )


def _read_local_csv(name: str) -> list[dict[str, Any]]:
    path = _DATA_DIR / f"{name}.csv"
    with path.open("r", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def find_unreconciled_invoices(
    entity_code: str = "ES_MADRID_HQ",
    min_amount_eur: float = 0.0,
    limit: int = 15,
) -> str:
    """Query pending supplier invoices in BigQuery by entity code and minimum total amount.

    Args:
        entity_code: Legal entity code (e.g. 'ES_MADRID_HQ', 'UK_LONDON_LTD', or 'all').
        min_amount_eur: Minimum invoice total in EUR (default 0.0).
        limit: Max invoices to return (default 15).

    Returns:
        JSON string with pending invoices including subtotal, VAT, anomaly_flag, and line_memo.
    """
    project, dataset = _resolve_project_and_dataset()
    ent_clean = (entity_code or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.supplier_invoices`"
            params: list[Any] = [
                bigquery.ScalarQueryParameter("min_amt", "FLOAT64", float(min_amount_eur)),
                bigquery.ScalarQueryParameter("lim", "INT64", int(limit)),
            ]
            where_ent = ""
            if ent_clean.lower() != "all":
                where_ent = "AND LOWER(entity_code) = LOWER(@ent) "
                params.append(bigquery.ScalarQueryParameter("ent", "STRING", ent_clean))
            sql = (
                f"SELECT invoice_id, counterparty_id, counterparty_name, entity_code, "
                f"expense_category, CAST(invoice_date AS STRING) AS invoice_date, "
                f"subtotal_eur, vat_eur, total_eur, po_reference, anomaly_flag, "
                f"line_memo, payment_status FROM {table_ref} "
                f"WHERE payment_status = 'PENDING_AUDIT' AND total_eur >= @min_amt {where_ent}"
                f"ORDER BY total_eur DESC LIMIT @lim"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.supplier_invoices",
                "count": len(rows),
                "invoices": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("supplier_invoices")
        if r["payment_status"] == "PENDING_AUDIT"
        and float(r["total_eur"]) >= float(min_amount_eur)
        and (ent_clean.lower() == "all" or r["entity_code"].lower() == ent_clean.lower())
    ][: int(limit)]
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows),
        "invoices": rows,
    })


def detect_ledger_anomalies(entity_code: str = "all") -> str:
    """Query supplier invoices in BigQuery that have non-NONE anomaly flags (VAT mismatch, duplicates, policy caps).

    Args:
        entity_code: Optional entity code filter (e.g. 'ES_MADRID_HQ', 'UK_LONDON_LTD', or 'all').

    Returns:
        JSON string listing anomalous invoices requiring audit hold.
    """
    project, dataset = _resolve_project_and_dataset()
    ent_clean = (entity_code or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.supplier_invoices`"
            where_ent = ""
            params: list[Any] = []
            if ent_clean.lower() != "all":
                where_ent = "AND LOWER(entity_code) = LOWER(@ent) "
                params.append(bigquery.ScalarQueryParameter("ent", "STRING", ent_clean))
            sql = (
                f"SELECT invoice_id, entity_code, counterparty_name, subtotal_eur, vat_eur, "
                f"total_eur, anomaly_flag, line_memo, payment_status "
                f"FROM {table_ref} WHERE anomaly_flag != 'NONE' {where_ent}"
                f"ORDER BY total_eur DESC LIMIT 20"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.supplier_invoices",
                "count": len(rows),
                "anomalies": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("supplier_invoices")
        if r["anomaly_flag"] != "NONE"
        and (ent_clean.lower() == "all" or r["entity_code"].lower() == ent_clean.lower())
    ][:20]
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows),
        "anomalies": rows,
    })


def get_treasury_policy(entity_code: str = "ES_MADRID_HQ", expense_category: str = "all") -> str:
    """Query entity treasury approval thresholds, expected VAT rates, and dual-signoff rules from BigQuery.

    Args:
        entity_code: Entity code (e.g. 'ES_MADRID_HQ', 'UK_LONDON_LTD', 'DE_BERLIN_GMBH').
        expense_category: Optional GL expense category filter or 'all'.

    Returns:
        JSON string with matching treasury policy rules.
    """
    project, dataset = _resolve_project_and_dataset()
    ent_clean = (entity_code or "ES_MADRID_HQ").strip()
    cat_clean = (expense_category or "all").strip()
    use_offline = os.environ.get("SEED_OFFLINE_MODE", "").lower() in {"1", "true", "yes"}
    if project and not use_offline:
        try:
            client = bigquery.Client(project=project)
            table_ref = f"`{project}.{dataset}.treasury_policies`"
            params: list[Any] = [bigquery.ScalarQueryParameter("ent", "STRING", ent_clean)]
            where_cat = ""
            if cat_clean.lower() != "all":
                where_cat = "AND LOWER(expense_category) = LOWER(@cat) "
                params.append(bigquery.ScalarQueryParameter("cat", "STRING", cat_clean))
            sql = (
                f"SELECT policy_id, entity_code, expense_category, max_auto_approve_eur, "
                f"requires_dual_signoff, vat_rate_expected_pct, sanctions_check_required "
                f"FROM {table_ref} WHERE LOWER(entity_code) = LOWER(@ent) {where_cat}"
                f"ORDER BY policy_id ASC LIMIT 15"
            )
            cfg = bigquery.QueryJobConfig(query_parameters=params)
            rows = [dict(r.items()) for r in client.query(sql, job_config=cfg).result()]
            return json.dumps({
                "status": "SUCCESS",
                "source": f"bigquery:{project}.{dataset}.treasury_policies",
                "count": len(rows),
                "policies": rows,
            }, default=str)
        except Exception as exc:
            fallback_error = _bq_error_hint(exc)
    else:
        fallback_error = _offline_reason(project)

    rows = [
        r for r in _read_local_csv("treasury_policies")
        if r["entity_code"].lower() == ent_clean.lower()
        and (cat_clean.lower() == "all" or r["expense_category"].lower() == cat_clean.lower())
    ][:15]
    return json.dumps({
        "status": "SUCCESS",
        "source": "local_csv_fallback",
        "fallback_reason": fallback_error,
        "count": len(rows),
        "policies": rows,
    })


TOOLS = [
    find_unreconciled_invoices,
    detect_ledger_anomalies,
    get_treasury_policy,
]

__all__ = [
    "TOOLS",
    "ACTION_TOOLS",
    "find_unreconciled_invoices",
    "detect_ledger_anomalies",
    "get_treasury_policy",
    "reconcile_invoice_to_ledger",
    "hold_payment_for_audit",
    "approve_verified_payout",
]
