"""Read-only preflight checks for the nine Olist CSV source files."""

from __future__ import annotations

import csv
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

try:  # Package import for tests and reusable calls.
    from .data_manifest import EXPECTED_FILES
except ImportError:  # Direct `python scripts/check_data.py` execution.
    from data_manifest import EXPECTED_FILES

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
LOG_DIR = ROOT / "logs"


def configure_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_DIR / "data_preflight.log", encoding="utf-8")],
    )


def inspect_csv(path: Path, expected: tuple[str, ...]) -> dict[str, object]:
    """Inspect header and count parseable data rows without loading the file into memory."""
    result: dict[str, object] = {"file": path.name, "present": path.is_file()}
    if not path.is_file():
        result["errors"] = ["Required source file is missing."]
        return result
    errors: list[str] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if header is None:
                errors.append("File is empty and has no header.")
                header = []
            blank_headers = [i for i, name in enumerate(header) if not name.strip()]
            duplicates = sorted({name for name in header if header.count(name) > 1})
            missing = [name for name in expected if name not in header]
            extra = [name for name in header if name not in expected]
            if blank_headers:
                errors.append(f"Blank header positions: {blank_headers}")
            if duplicates:
                errors.append(f"Duplicate headers: {duplicates}")
            if missing:
                errors.append(f"Missing required headers: {missing}")
            row_count = 0
            for line_num, row in enumerate(reader, start=2):
                if len(row) != len(header):
                    errors.append(f"Row {line_num} has {len(row)} fields; header has {len(header)}.")
                    break
                row_count += 1
            result.update({"headers": header, "extra_headers": extra, "row_count": row_count})
    except (OSError, UnicodeError, csv.Error, StopIteration) as exc:
        errors.append(f"Could not parse CSV: {exc}")
    result["errors"] = errors
    result["valid"] = not errors
    return result


def run() -> int:
    configure_logging()
    checks = [inspect_csv(RAW_DIR / filename, headers) for filename, headers in EXPECTED_FILES.items()]
    valid = all(check.get("valid", False) for check in checks)
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "raw_directory": str(RAW_DIR),
        "valid": valid,
        "files": checks,
    }
    report_path = LOG_DIR / "data_preflight.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for item in checks:
        logging.info("%s: %s", item["file"], "OK" if item.get("valid") else "; ".join(item.get("errors", [])))
    logging.info("Preflight %s; report: %s", "passed" if valid else "failed", report_path)
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(run())
