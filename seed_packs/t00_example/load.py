"""Idempotent BigQuery & Cloud Storage seeding script for Seed Pack t00_example."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery
from google.cloud import storage

_PACK_DIR = Path(__file__).resolve().parent
_DATA_DIR = _PACK_DIR / "data"
_DATASET_ID = "seed_t00"


def seed_bigquery(project_id: str, location: str = "EU") -> list[str]:
    """Create dataset `seed_t00` and load `menu` and `daily_sales` tables idempotently."""
    client = bigquery.Client(project=project_id)
    dataset_ref = bigquery.Dataset(f"{project_id}.{_DATASET_ID}")
    dataset_ref.location = location
    client.create_dataset(dataset_ref, exists_ok=True)

    tables = {
        "menu": (
            _DATA_DIR / "menu.json",
            [
                bigquery.SchemaField("item_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("name", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("category", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("price_gbp", "FLOAT", mode="REQUIRED"),
                bigquery.SchemaField("caffeine_mg", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("oat_milk_available", "BOOLEAN", mode="REQUIRED"),
                bigquery.SchemaField("in_stock", "BOOLEAN", mode="REQUIRED"),
            ],
        ),
        "daily_sales": (
            _DATA_DIR / "daily_sales.json",
            [
                bigquery.SchemaField("sale_date", "DATE", mode="REQUIRED"),
                bigquery.SchemaField("store_location", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("top_item", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("cups_sold", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("revenue_gbp", "FLOAT", mode="REQUIRED"),
                bigquery.SchemaField("bean_stock_kg", "FLOAT", mode="REQUIRED"),
            ],
        ),
    }

    loaded: list[str] = []
    for table_name, (json_path, schema) in tables.items():
        rows = json.loads(json_path.read_text(encoding="utf-8"))
        table_id = f"{project_id}.{_DATASET_ID}.{table_name}"
        job_config = bigquery.LoadJobConfig(
            schema=schema,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        job = client.load_table_from_json(rows, table_id, job_config=job_config)
        job.result()
        loaded.append(f"{table_id} ({len(rows)} rows)")
    return loaded


def seed_gcs(project_id: str, bucket_uri: str | None) -> list[str]:
    """Optionally upload data files to STAGING_BUCKET under `seed_packs/t00_example/`."""
    if not bucket_uri:
        return []
    bucket_name = bucket_uri.replace("gs://", "").strip("/").split("/")[0]
    if not bucket_name or bucket_name.startswith("your-"):
        return []
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    uploaded: list[str] = []
    for file_path in sorted(_DATA_DIR.glob("*.json")):
        blob_name = f"seed_packs/t00_example/{file_path.name}"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(file_path))
        uploaded.append(f"gs://{bucket_name}/{blob_name}")
    return uploaded


def _run() -> None:
    load_dotenv(_PACK_DIR.parent.parent / ".env")
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    if not project_id or "your-gcp-project-id" in project_id:
        raise SystemExit(
            "ERROR: GOOGLE_CLOUD_PROJECT is not set. Copy .env.example to .env and set GOOGLE_CLOUD_PROJECT."
        )
    bq_location = os.environ.get("BQ_LOCATION", "EU").strip() or "EU"
    staging_bucket = os.environ.get("STAGING_BUCKET", "").strip()

    print(f"[seed:t00_example] Seeding BigQuery dataset '{_DATASET_ID}' in project '{project_id}' (location={bq_location})...")
    bq_tables = seed_bigquery(project_id=project_id, location=bq_location)
    for item in bq_tables:
        print(f"  + BigQuery table loaded: {item}")

    try:
        gcs_objects = seed_gcs(project_id=project_id, bucket_uri=staging_bucket)
        for obj in gcs_objects:
            print(f"  + GCS object uploaded:   {obj}")
    except Exception as exc:
        print(f"  ! Optional GCS upload skipped ({exc})")

    print("[seed:t00_example] Done.")


def main() -> None:
    try:
        _run()
    except Exception as exc:
        from app.preflight import format_error

        raise SystemExit(format_error(exc)) from None


if __name__ == "__main__":
    main()
