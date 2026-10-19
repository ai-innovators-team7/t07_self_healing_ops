"""Idempotent BigQuery and Cloud Storage loader for Seed Pack t01_campaign_orchestrator."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery
from google.cloud import storage

_PACK_DIR = Path(__file__).resolve().parent
_DATA_DIR = _PACK_DIR / "data"
_DATASET_ID = "seed_t01"
_GCS_PREFIX = "seed/t01/"


def seed_bigquery(project_id: str, location: str = "EU") -> list[str]:
    """Create dataset `seed_t01` and load all CSV tables idempotently."""
    client = bigquery.Client(project=project_id)
    dataset_ref = bigquery.Dataset(f"{project_id}.{_DATASET_ID}")
    dataset_ref.location = location
    client.create_dataset(dataset_ref, exists_ok=True)

    loaded: list[str] = []
    for csv_path in sorted(_DATA_DIR.glob("*.csv")):
        table_name = csv_path.stem
        table_id = f"{project_id}.{_DATASET_ID}.{table_name}"
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            autodetect=True,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        with csv_path.open("rb") as fp:
            job = client.load_table_from_file(fp, table_id, job_config=job_config)
        job.result()
        table_obj = client.get_table(table_id)
        loaded.append(f"{table_id} ({table_obj.num_rows} rows)")
    return loaded


def seed_gcs(project_id: str, bucket_uri: str | None) -> list[str]:
    """Optionally upload CSV files to SEED_BUCKET under `seed/t01/`."""
    if not bucket_uri:
        return []
    bucket_name = bucket_uri.replace("gs://", "").strip("/").split("/")[0]
    if not bucket_name or bucket_name.startswith("your-"):
        return []
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    uploaded: list[str] = []
    for csv_path in sorted(_DATA_DIR.glob("*.csv")):
        blob_name = f"{_GCS_PREFIX}{csv_path.name}"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(csv_path))
        uploaded.append(f"gs://{bucket_name}/{blob_name}")
    return uploaded


def _run() -> None:
    load_dotenv(_PACK_DIR.parent.parent / ".env")
    project_id = (
        os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
        or os.environ.get("AGENT_ENGINE_PROJECT", "").strip()
    )
    if not project_id or "your-gcp-project-id" in project_id or "your-project-id" in project_id:
        raise SystemExit(
            "ERROR: GOOGLE_CLOUD_PROJECT is not set. Run `cp .env.example .env`, set "
            "GOOGLE_CLOUD_PROJECT=<your project id>, then re-run `make seed PACK=t01`."
        )
    bq_location = os.environ.get("BQ_LOCATION", "EU").strip() or "EU"
    seed_bucket = (
        os.environ.get("SEED_BUCKET", "").strip()
        or os.environ.get("STAGING_BUCKET", "").strip()
    )

    print(
        f"[seed:t01_campaign_orchestrator] Loading BigQuery dataset '{_DATASET_ID}' "
        f"in project '{project_id}' (location={bq_location})..."
    )
    for item in seed_bigquery(project_id=project_id, location=bq_location):
        print(f"  + BigQuery table loaded: {item}")

    if seed_bucket:
        try:
            for obj in seed_gcs(project_id=project_id, bucket_uri=seed_bucket):
                print(f"  + GCS object uploaded:   {obj}")
        except Exception as exc:  # optional step: BigQuery tables are already loaded
            print(f"  ! Optional GCS upload to {seed_bucket} skipped ({type(exc).__name__}: {exc})")

    print("[seed:t01_campaign_orchestrator] Done.")


def main() -> None:
    """CLI entrypoint for `python -m seed_packs.t01_campaign_orchestrator.load` / `make seed PACK=t01`."""
    try:
        _run()
    except Exception as exc:
        from app.preflight import format_error

        raise SystemExit(format_error(exc)) from None


if __name__ == "__main__":
    main()
