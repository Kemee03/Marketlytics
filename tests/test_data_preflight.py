"""Unit tests for CSV header and row-shape validation (no Olist data required)."""

import tempfile
import unittest
from pathlib import Path

from scripts.check_data import inspect_csv


class DataPreflightTests(unittest.TestCase):
    def inspect(self, content: str, expected: tuple[str, ...]) -> dict[str, object]:
        # Keep fixtures under the repository so restricted Windows temp paths do not block tests.
        fixture_root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(dir=fixture_root) as directory:
            path = Path(directory) / "fixture.csv"
            path.write_text(content, encoding="utf-8", newline="")
            return inspect_csv(path, expected)

    def test_accepts_valid_csv_and_counts_rows(self) -> None:
        result = self.inspect("id,value\n1,hello\n2,world\n", ("id", "value"))
        self.assertTrue(result["valid"])
        self.assertEqual(result["row_count"], 2)

    def test_rejects_missing_required_header(self) -> None:
        result = self.inspect("id\n1\n", ("id", "value"))
        self.assertFalse(result["valid"])
        self.assertIn("Missing required headers", result["errors"][0])

    def test_rejects_malformed_row_width(self) -> None:
        result = self.inspect("id,value\n1\n", ("id", "value"))
        self.assertFalse(result["valid"])
        self.assertIn("Row 2 has 1 fields", result["errors"][0])


if __name__ == "__main__":
    unittest.main()
