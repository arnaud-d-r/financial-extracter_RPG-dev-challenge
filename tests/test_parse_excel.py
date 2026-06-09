from __future__ import annotations

import datetime
from pathlib import Path
import unittest
from unittest.mock import patch

from extractors.models import TransactionCategory
from extractors.parse_excel import parse_excel


class FakeInvoiceFrame:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def iterrows(self):
        for index, row in enumerate(self._rows):
            yield index, row


class ParseExcelTests(unittest.TestCase):

    @patch("extractors.parse_excel.pd.read_excel")
    def test_parse_excel_happy_path_invoice(self, mock_read_excel) -> None:
        """Test standard Excel row parsing with all fields populated for an invoice."""
        simulated_row = {
            "vendor": "BrightPath Marketing",
            "description": "Social media graphics -- January",
            "amount": 3500.0,
            "date": "2025-01-05",
            "date paid": "2025-01-18"
        }
        mock_read_excel.return_value = FakeInvoiceFrame([simulated_row])
        
        # Patch downstream helper methods if they require strict datetime objects,
        # but if your _parse_date handles standard string types or ISO dates, this will pass seamlessly.
        with patch("extractors.parse_excel._parse_date", side_effect=lambda v: datetime.date(2025, 1, 5) if "05" in str(v) else datetime.date(2025, 1, 18)):
            result = parse_excel(Path("mock_invoices.xlsx"), category=TransactionCategory.INVOICE)
            
        self.assertEqual(len(result.records), 1)
        record = result.records[0]
        self.assertEqual(record.vendor, "BrightPath Marketing")
        self.assertEqual(record.description, "Social media graphics -- January")
        self.assertEqual(record.amount, 3500.0)
        self.assertEqual(record.date, datetime.date(2025, 1, 5))
        self.assertEqual(record.invoice_paid_date, datetime.date(2025, 1, 18))
        self.assertEqual(record.category, TransactionCategory.INVOICE)

    @patch("extractors.parse_excel.pd.read_excel")
    def test_parse_excel_column_synonyms(self, mock_read_excel) -> None:
        """Edge Case: Ensure synonym tracking hits alternative naming configurations (e.g., 'merchant', 'price')."""
        simulated_row = {
            "merchant": "Alternative Vendor Inc",
            "details": "Consulting work",
            "price": "1200.50",
            "date sent": "2025-02-10",
            "payment date": "2025-02-20"
        }
        mock_read_excel.return_value = FakeInvoiceFrame([simulated_row])
        
        with patch("extractors.parse_excel._parse_date", return_value=datetime.date(2025, 2, 12)):
            result = parse_excel(Path("synonyms.xlsx"), category=TransactionCategory.INVOICE)
            
        self.assertEqual(len(result.records), 1)
        record = result.records[0]
        # Assertions prove your ColumnMatching dictionary matched alternate headers perfectly
        self.assertEqual(record.vendor, "Alternative Vendor Inc")
        self.assertEqual(record.description, "Consulting work")
        self.assertEqual(record.amount, 1200.50)

    @patch("extractors.parse_excel.pd.read_excel")
    def test_parse_excel_ignores_paid_date_if_not_invoice(self, mock_read_excel) -> None:
        """Edge Case: Paid date must remain None if the run category isn't an INVOICE."""
        simulated_row = {
            "vendor": "Hardware Store",
            "description": "Tools",
            "amount": 45.22,
            "date": "2025-03-01",
            "date paid": "2025-03-02" # Provided in sheet, but should be blocked by condition
        }
        mock_read_excel.return_value = FakeInvoiceFrame([simulated_row])
        
        with patch("extractors.parse_excel._parse_date", return_value=datetime.date(2025, 3, 1)):
            result = parse_excel(Path("receipts.xlsx"), category=TransactionCategory.RECEIPT)
            
        self.assertEqual(len(result.records), 1)
        self.assertIsNone(result.records[0].invoice_paid_date)

    @patch("extractors.parse_excel.pd.read_excel")
    def test_parse_excel_handles_missing_optional_values(self, mock_read_excel) -> None:
        """Edge Case: Ensure rows containing missing or completely empty elements are dropped."""
        simulated_row = {
            "vendor": None,
            "description": None,
            "amount": None,
            "date": None,
            "date paid": None
        }
        mock_read_excel.return_value = FakeInvoiceFrame([simulated_row])
        
        with patch("extractors.parse_excel._parse_date", return_value=None):
            result = parse_excel(Path("empty_rows.xlsx"), category=TransactionCategory.INVOICE)
            
        self.assertEqual(len(result.records), 0)


    @patch("extractors.parse_excel.pd.read_excel")
    def test_parse_excel_multi_row_accumulation(self, mock_read_excel) -> None:
        """Verify that multi-row spreadsheets translate fully into a complete record stack."""
        rows = [
            {"vendor": "V1", "description": "D1", "amount": 10.0, "date": "2025-01-01"},
            {"vendor": "V2", "description": "D2", "amount": 20.0, "date": "2025-01-02"},
            {"vendor": "V3", "description": "D3", "amount": 30.0, "date": "2025-01-03"}
        ]
        mock_read_excel.return_value = FakeInvoiceFrame(rows)
        
        result = parse_excel(Path("bulk.xlsx"), category=TransactionCategory.RECEIPT)
        self.assertEqual(len(result.records), 3)
        self.assertEqual(result.records[0].vendor, "V1")
        self.assertEqual(result.records[2].vendor, "V3")
        
    @patch("extractors.parse_excel.pd.read_excel")
    def test_parse_excel_filters_pandas_nan_and_nat(self, mock_read_excel) -> None:
        """
        Ensures blank Excel cells (parsed by pandas as float('nan') or NaT)
        are cleanly resolved to Python None instead of string 'nan'.
        """
        import pandas as pd
        
        # Simulating how pandas reads a row with empty cells
        corrupted_row = {
            "vendor": float("nan"),      # Missing text cell -> float nan
            "description": "Valid Item",
            "amount": 120.00,
            "date": pd.NaT               # Missing date cell -> pandas NaT
        }
        mock_read_excel.return_value = FakeInvoiceFrame([corrupted_row])
        
        result = parse_excel(Path("test.xlsx"), category=TransactionCategory.RECEIPT)
        
        self.assertEqual(len(result.records), 1)
        record = result.records[0]
        
        # Verify your code successfully forced them to None, preventing data leakage
        self.assertIsNone(record.vendor, "Should convert float('nan') to None")
        self.assertIsNone(record.date, "Should convert pd.NaT to None")


if __name__ == "__main__":
    unittest.main()