"""Validate Olist inputs and transactionally replace PostgreSQL staging tables."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

try:  # Package imports for tests and reusable calls.
    from .check_data import run as run_preflight
    from .data_manifest import EXPECTED_FILES
except ImportError:  # Direct `python scripts/load_staging.py` execution.
    from check_data import run as run_preflight
    from data_manifest import EXPECTED_FILES

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
LOG_DIR = ROOT / "logs"
CHUNKSIZE = 100_000


def database_url() -> str:
    """Build a SQLAlchemy URL from environment configuration without logging secrets."""
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured
    required = ("PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD")
    absent = [key for key in required if not os.getenv(key)]
    if absent:
        raise RuntimeError(f"Database configuration missing: {', '.join(absent)}")
    port = os.getenv("PGPORT", "5432")
    from sqlalchemy.engine import URL

    return URL.create(
        "postgresql+psycopg2",
        username=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        host=os.environ["PGHOST"],
        port=int(port),
        database=os.environ["PGDATABASE"],
    ).render_as_string(hide_password=False)


def load_table(connection, filename: str, expected_headers: tuple[str, ...]) -> int:
    """Load one CSV in bounded chunks with source fields preserved as strings."""
    path = RAW_DIR / filename
    table_name = Path(filename).stem.removeprefix("olist_").removesuffix("_dataset")
    table_name = {"product_category_name_translation": "product_category_translation"}.get(table_name, table_name)
    first = True
    count = 0
    for chunk in pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=CHUNKSIZE, encoding="utf-8-sig"):
        if tuple(chunk.columns) != expected_headers:
            missing = [column for column in expected_headers if column not in chunk.columns]
            if missing:
                raise ValueError(f"{filename} changed after preflight; missing columns: {missing}")
        chunk.columns = [column.strip().lower() for column in chunk.columns]
        chunk.to_sql(
            table_name,
            con=connection,
            schema="staging",
            if_exists="replace" if first else "append",
            index=False,
            method="multi",
            chunksize=2_000,
        )
        first = False
        count += len(chunk)
    if first:  # Header-only source: create a correctly shaped empty text table.
        empty = pd.DataFrame(columns=expected_headers)
        empty.to_sql(table_name, con=connection, schema="staging", if_exists="replace", index=False)
    return count


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_DIR / "staging_load.log", encoding="utf-8")])
    load_dotenv(ROOT / ".env")
    if run_preflight() != 0:
        logging.error("Preflight failed; staging load was not started.")
        return 1
    engine = None
    counts: dict[str, int] = {}
    try:
        engine = create_engine(database_url(), pool_pre_ping=True)
        with engine.begin() as connection:
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS staging"))
            for filename, headers in EXPECTED_FILES.items():
                counts[filename] = load_table(connection, filename, headers)
                logging.info("Loaded %s rows from %s", counts[filename], filename)
        report = {"loaded_at_utc": datetime.now(timezone.utc).isoformat(), "schema": "staging", "rows": counts}
        (LOG_DIR / "staging_load.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        logging.info("Staging load committed successfully.")
        return 0
    except Exception:
        logging.exception("Staging load failed; database transaction rolled back.")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
