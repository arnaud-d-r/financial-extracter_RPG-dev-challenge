from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from extractors.parse_invoices import parse_invoices


REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeInvoiceFrame:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def iterrows(self):
        for index, row in enumerate(self._rows):
            yield index, row


class ParseInvoicesTests(unittest.TestCase):
    def test_parse_invoices_converts_rows_into_records(self) -> None:
        fake_pandas = types.SimpleNamespace(
            read_excel=lambda path: FakeInvoiceFrame(
                [
                    {"vendor": "Acme Studio", "amount": 125.5, "category": "design", "date": "2026-01-15"},
                    {"merchant": "Blue Coffee", "total": 8, "category": "meals", "date": None},
                ]
            )
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            workbook = Path(temp_dir) / "invoices.xlsx"
            workbook.write_bytes(b"placeholder")

            with patch.dict(sys.modules, {"pandas": fake_pandas}):
                result = parse_invoices(workbook)

        self.assertEqual(result.source_file, "invoices.xlsx")
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.records[0].vendor, "Acme Studio")
        self.assertEqual(result.records[0].amount, 125.5)
        self.assertEqual(result.records[1].vendor, "Blue Coffee")
        self.assertEqual(result.records[1].amount, 8.0)

    def test_parse_invoices_reads_real_workbook(self) -> None:
        workbook = REPO_ROOT / "shoebox" / "invoices.xlsx"

        result = parse_invoices(workbook)

        self.assertEqual(result.source_file, "invoices.xlsx")
        self.assertEqual(len(result.records), 9)
        self.assertEqual(result.records[0].vendor, "BrightPath Marketing")
        self.assertEqual(result.records[0].category, "Social media graphics -- January")
        self.assertEqual(result.records[0].amount, 3500.0)
        self.assertEqual(result.records[0].date, "1/5/2025")


if __name__ == "__main__":
    unittest.main()
