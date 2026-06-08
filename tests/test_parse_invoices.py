from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import datetime

from extractors.models import Transaction, TransactionCategory, ExtractionResult
from extractors.parse_excel import parse_excel


REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeInvoiceFrame:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def iterrows(self):
        for index, row in enumerate(self._rows):
            yield index, row


class ParseInvoicesTests(unittest.TestCase):

    def test_parse_invoices_reads_real_workbook(self) -> None:
        workbook = REPO_ROOT / "shoebox" / "invoices.xlsx"

        result = parse_excel(workbook, category=TransactionCategory.INVOICE)

        self.assertEqual(result.source_file, "invoices.xlsx")
        self.assertEqual(len(result.records), 9)
        self.assertEqual(result.records[0].vendor, "BrightPath Marketing")
        self.assertEqual(result.records[0].description, "Social media graphics -- January")
        self.assertEqual(result.records[0].amount, 3500.0)
        self.assertEqual(result.records[0].date, datetime.datetime(2025, 1, 5).date())
        self.assertEqual(result.records[0].invoice_paid_date, datetime.datetime(2025, 1, 18).date())
        self.assertEqual(result.records[0].category, TransactionCategory.INVOICE)


if __name__ == "__main__":
    unittest.main()
