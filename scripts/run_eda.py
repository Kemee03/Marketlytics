"""Command-line entry point for reproducible Marketlytics EDA outputs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.eda import run_eda  # noqa: E402


if __name__ == "__main__":
    print(json.dumps(run_eda(), indent=2, default=str))
