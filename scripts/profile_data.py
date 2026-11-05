"""Profile the supplied Olist CSVs and produce reproducible quality evidence."""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from data_manifest import EXPECTED_FILES

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
REPORT_DIR = ROOT / "reports"
CHUNK_SIZE = 100_000

PRIMARY_KEYS: dict[str, tuple[str, ...] | None] = {
    "olist_customers_dataset.csv": ("customer_id",),
    "olist_geolocation_dataset.csv": None,  # Source provides no unique row identifier.
    "olist_order_items_dataset.csv": ("order_id", "order_item_id"),
    "olist_order_payments_dataset.csv": ("order_id", "payment_sequential"),
    # review_id repeats across orders in this source; the pair is unique.
    "olist_order_reviews_dataset.csv": ("review_id", "order_id"),
    "olist_orders_dataset.csv": ("order_id",),
    "olist_products_dataset.csv": ("product_id",),
    "olist_sellers_dataset.csv": ("seller_id",),
    "product_category_name_translation.csv": ("product_category_name",),
}

FOREIGN_KEYS = (
    ("olist_orders_dataset.csv", "customer_id", "olist_customers_dataset.csv", "customer_id"),
    ("olist_order_items_dataset.csv", "order_id", "olist_orders_dataset.csv", "order_id"),
    ("olist_order_items_dataset.csv", "product_id", "olist_products_dataset.csv", "product_id"),
    ("olist_order_items_dataset.csv", "seller_id", "olist_sellers_dataset.csv", "seller_id"),
    ("olist_order_payments_dataset.csv", "order_id", "olist_orders_dataset.csv", "order_id"),
    ("olist_order_reviews_dataset.csv", "order_id", "olist_orders_dataset.csv", "order_id"),
)

GEOGRAPHY_LOOKUPS = (
    ("olist_customers_dataset.csv", "customer_zip_code_prefix", "customer_state"),
    ("olist_sellers_dataset.csv", "seller_zip_code_prefix", "seller_state"),
)

NUMERIC_COLUMNS = {
    "olist_order_items_dataset.csv": ("order_item_id", "price", "freight_value"),
    "olist_order_payments_dataset.csv": ("payment_sequential", "payment_installments", "payment_value"),
    "olist_order_reviews_dataset.csv": ("review_score",),
    "olist_products_dataset.csv": (
        "product_name_lenght", "product_description_lenght", "product_photos_qty",
        "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm",
    ),
    "olist_geolocation_dataset.csv": ("geolocation_lat", "geolocation_lng"),
}

DATETIME_COLUMNS = {
    "olist_order_items_dataset.csv": ("shipping_limit_date",),
    "olist_order_payments_dataset.csv": (),
    "olist_order_reviews_dataset.csv": ("review_creation_date", "review_answer_timestamp"),
    "olist_orders_dataset.csv": (
        "order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
        "order_delivered_customer_date", "order_estimated_delivery_date",
    ),
}


def profile_file(filename: str, headers: tuple[str, ...]) -> tuple[dict, set | None]:
    """Count blanks, key violations, numeric parsing issues, and timestamp coverage in chunks."""
    key_columns = PRIMARY_KEYS[filename]
    key_values: set | None = None
    if filename in ("olist_customers_dataset.csv", "olist_orders_dataset.csv", "olist_products_dataset.csv", "olist_sellers_dataset.csv", "olist_geolocation_dataset.csv"):
        key_values = set()
    seen_keys: set[tuple[str, ...]] = set()
    duplicate_key_rows = 0
    missing_key_rows = 0
    row_count = 0
    blanks: Counter[str] = Counter()
    numeric = {column: {"invalid": 0, "count": 0, "min": None, "max": None} for column in NUMERIC_COLUMNS.get(filename, ())}
    timestamps = {column: {"invalid": 0, "count": 0, "min": None, "max": None} for column in DATETIME_COLUMNS.get(filename, ())}

    for chunk in pd.read_csv(RAW_DIR / filename, dtype=str, keep_default_na=False,
                             encoding="utf-8-sig", chunksize=CHUNK_SIZE):
        row_count += len(chunk)
        blanks.update((chunk == "").sum().to_dict())

        if key_columns:
            for row in chunk.loc[:, list(key_columns)].itertuples(index=False, name=None):
                key = tuple(value.strip() for value in row)
                if any(not value for value in key):
                    missing_key_rows += 1
                    continue
                if key in seen_keys:
                    duplicate_key_rows += 1
                else:
                    seen_keys.add(key)
            if key_values is not None:
                key_values.update(chunk[key_columns[0]].loc[chunk[key_columns[0]] != ""].tolist())
        elif filename == "olist_geolocation_dataset.csv":
            prefixes = chunk["geolocation_zip_code_prefix"].str.strip().str.zfill(5)
            states = chunk["geolocation_state"].str.strip().str.upper()
            key_values.update(zip(prefixes, states))

        for column, stats in numeric.items():
            source = chunk[column].str.strip()
            parsed = pd.to_numeric(source.where(source != ""), errors="coerce")
            stats["invalid"] += int(((source != "") & parsed.isna()).sum())
            valid = parsed.dropna()
            stats["count"] += int(valid.size)
            if not valid.empty:
                low, high = float(valid.min()), float(valid.max())
                stats["min"] = low if stats["min"] is None else min(stats["min"], low)
                stats["max"] = high if stats["max"] is None else max(stats["max"], high)

        for column, stats in timestamps.items():
            source = chunk[column].str.strip()
            parsed = pd.to_datetime(source.where(source != ""), errors="coerce", utc=True, format="mixed")
            stats["invalid"] += int(((source != "") & parsed.isna()).sum())
            valid = parsed.dropna()
            stats["count"] += int(valid.size)
            if not valid.empty:
                low, high = valid.min().isoformat(), valid.max().isoformat()
                stats["min"] = low if stats["min"] is None else min(stats["min"], low)
                stats["max"] = high if stats["max"] is None else max(stats["max"], high)

    result = {
        "rows": row_count,
        "columns": len(headers),
        "blank_cells": {column: int(blanks[column]) for column in headers if blanks[column]},
        "blank_cell_count": int(sum(blanks.values())),
        "primary_key": list(key_columns) if key_columns else None,
        "primary_key_duplicate_rows": duplicate_key_rows if key_columns else None,
        "primary_key_missing_rows": missing_key_rows if key_columns else None,
        "numeric_columns": numeric,
        "datetime_columns": timestamps,
    }
    return result, key_values


def count_unmatched(filename: str, column: str, parent_keys: set[str]) -> dict[str, int]:
    """Count blank and nonblank unmatched foreign-key values without retaining child rows."""
    blank = unmatched = total = 0
    for chunk in pd.read_csv(RAW_DIR / filename, usecols=[column], dtype=str,
                             keep_default_na=False, encoding="utf-8-sig", chunksize=CHUNK_SIZE):
        values = chunk[column].str.strip()
        blank += int((values == "").sum())
        nonblank = values[values != ""]
        total += int(nonblank.size)
        unmatched += int((~nonblank.isin(parent_keys)).sum())
    return {"nonblank_values": total, "blank_values": blank, "unmatched_values": unmatched}


def count_unmatched_geography(filename: str, zip_column: str, state_column: str, geo_pairs: set) -> dict[str, int]:
    """Measure how many customer/seller locations lack an exact ZIP-prefix/state geolocation row."""
    unmatched_rows = 0
    seen_pairs: set[tuple[str, str]] = set()
    unmatched_pairs: set[tuple[str, str]] = set()
    rows = 0
    for chunk in pd.read_csv(RAW_DIR / filename, usecols=[zip_column, state_column], dtype=str,
                             keep_default_na=False, encoding="utf-8-sig", chunksize=CHUNK_SIZE):
        prefixes = chunk[zip_column].str.strip().str.zfill(5)
        states = chunk[state_column].str.strip().str.upper()
        pairs = zip(prefixes, states)
        for pair in pairs:
            rows += 1
            seen_pairs.add(pair)
            if pair not in geo_pairs:
                unmatched_rows += 1
                unmatched_pairs.add(pair)
    return {
        "source_rows": rows,
        "distinct_source_pairs": len(seen_pairs),
        "unmatched_rows": unmatched_rows,
        "unmatched_distinct_pairs": len(unmatched_pairs),
    }


def markdown_report(report: dict) -> str:
    lines = [
        "# Olist data quality profile",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        "This report was computed from the nine user-supplied source CSVs. Blank strings are counted as missing; source records are not modified.",
        "",
        "## Source inventory",
        "",
        "| File | Rows | Columns | Blank cells | Declared-key duplicate rows | Declared-key missing rows |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for filename, details in report["files"].items():
        duplicates = "—" if details["primary_key_duplicate_rows"] is None else f"{details['primary_key_duplicate_rows']:,}"
        missing = "—" if details["primary_key_missing_rows"] is None else f"{details['primary_key_missing_rows']:,}"
        lines.append(f"| `{filename}` | {details['rows']:,} | {details['columns']} | {details['blank_cell_count']:,} | {duplicates} | {missing} |")

    lines.extend(["", "## Missingness by field", "", "Only fields with blanks are listed. Missingness in delivery timestamps and review text is preserved for later rule-based treatment.", ""])
    for filename, details in report["files"].items():
        if not details["blank_cells"]:
            continue
        lines.extend([f"### `{filename}`", "", "| Field | Blank rows | Share of file |", "|---|---:|---:|"])
        for column, count in sorted(details["blank_cells"].items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"| `{column}` | {count:,} | {count / details['rows']:.1%} |")
        lines.append("")

    lines.extend(["## Referential integrity", "", "| Child relation | Parent relation | Nonblank child values | Blank child values | Unmatched values |", "|---|---|---:|---:|---:|"])
    for item in report["foreign_keys"]:
        child = f"{item['child_file']}:{item['child_column']}"
        parent = f"{item['parent_file']}:{item['parent_column']}"
        counts = item["counts"]
        lines.append(f"| `{child}` | `{parent}` | {counts['nonblank_values']:,} | {counts['blank_values']:,} | {counts['unmatched_values']:,} |")

    lines.extend(["", "## Geography lookup coverage", "", "Geography is matched on normalized ZIP prefix plus state because some ZIP prefixes occur in more than one state.", "", "| Source | Source rows | Distinct ZIP/state pairs | Rows without a geolocation match | Unmatched distinct pairs |", "|---|---:|---:|---:|---:|"])
    for item in report["geography_coverage"]:
        counts = item["counts"]
        lines.append(f"| `{item['source_file']}` | {counts['source_rows']:,} | {counts['distinct_source_pairs']:,} | {counts['unmatched_rows']:,} | {counts['unmatched_distinct_pairs']:,} |")

    lines.extend(["", "## Type parsing checks", "", "Numeric and datetime fields were parsed for quality assessment only; raw staging remains text-preserving.", ""])
    for filename, details in report["files"].items():
        checks = [("numeric", details["numeric_columns"]), ("datetime", details["datetime_columns"])]
        for kind, fields in checks:
            invalid = {column: stats["invalid"] for column, stats in fields.items() if stats["invalid"]}
            if invalid:
                lines.append(f"- `{filename}` {kind} parse failures: " + ", ".join(f"`{column}` {count:,}" for column, count in invalid.items()))
    if not any(
        stats["invalid"]
        for details in report["files"].values()
        for fields in (details["numeric_columns"], details["datetime_columns"])
        for stats in fields.values()
    ):
        lines.append("No nonblank numeric or datetime parse failures were observed in the profiled fields.")

    lines.extend([
        "",
        "## Modeling implications",
        "",
        "- `order_items` grain is one order line (`order_id`, `order_item_id`); item revenue and freight belong at this grain.",
        "- `order_payments` grain is one payment sequence per order; aggregate to order before joining to order-line revenue.",
        "- `order_reviews` is a separate order-review grain; do not join raw payments, items, and reviews together before aggregation.",
        "- Geolocation has no supplied unique row identifier. Model it as a ZIP-prefix lookup after profiling/choosing an explicit aggregation rule.",
        "- Customer and seller locations do not all match the geolocation file. Model a documented unknown/missing geography record instead of dropping those entities or forcing a false match.",
        "- Blank values are retained in staging. A blank delivery timestamp can mean an order was not delivered; it must not be imputed as zero days.",
        "- Revenue is the sum of item `price`; freight is reported separately. These public records do not support a profit calculation.",
        "",
        "## Limitations",
        "",
        "This is a source-quality profile, not a statistical business findings report. It does not assert that a source field is correct merely because it parses. Business metrics and recommendations are deferred until transformations and metric definitions are validated.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    files: dict[str, dict] = {}
    parent_keys: dict[str, set[str]] = {}
    for filename, headers in EXPECTED_FILES.items():
        details, keys = profile_file(filename, headers)
        files[filename] = details
        if keys is not None:
            parent_keys[filename] = keys
        logging.info("Profiled %s rows from %s", details["rows"], filename)

    foreign_keys = []
    for child_file, child_column, parent_file, parent_column in FOREIGN_KEYS:
        counts = count_unmatched(child_file, child_column, parent_keys[parent_file])
        foreign_keys.append({
            "child_file": child_file,
            "child_column": child_column,
            "parent_file": parent_file,
            "parent_column": parent_column,
            "counts": counts,
        })

    geo_pairs = parent_keys["olist_geolocation_dataset.csv"]
    geography_coverage = []
    for filename, zip_column, state_column in GEOGRAPHY_LOOKUPS:
        geography_coverage.append({
            "source_file": filename,
            "zip_column": zip_column,
            "state_column": state_column,
            "counts": count_unmatched_geography(filename, zip_column, state_column, geo_pairs),
        })

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "raw_directory": str(RAW_DIR),
        "files": files,
        "foreign_keys": foreign_keys,
        "geography_coverage": geography_coverage,
    }
    (REPORT_DIR / "data_quality_profile.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (REPORT_DIR / "data_quality_profile.md").write_text(markdown_report(report), encoding="utf-8")
    logging.info("Wrote %s and %s", REPORT_DIR / "data_quality_profile.md", REPORT_DIR / "data_quality_profile.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
