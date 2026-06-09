from __future__ import annotations

import datetime
from pathlib import Path
import unittest
from unittest.mock import patch

from extractors.models import TransactionCategory, PaymentMethod
from extractors.parse_pdf import parse_pdf


class FakePdfPage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class FakePdfDocument:
    def __init__(self, pages: list[FakePdfPage]) -> None:
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class ParsePdfTests(unittest.TestCase):

    @patch("extractors.parse_pdf.pdfplumber.open")
    def test_parse_pdf_extracts_valid_transaction_lines(self, mock_pdf_open) -> None:
        """Test that standard transaction rows matching the TXN pattern are extracted correctly."""
        simulated_text = """
        STATEMENT PERIOD: JAN 01 - MAR 31, 2025
        
        TXN-99831 JAN 05 GOOGLE *WORKSPACE 8.28
        TXN-11204 FEB 06 ADOBE *CREATIVE CL 74.99
        """
        mock_pdf_open.return_value = FakePdfDocument([FakePdfPage(simulated_text)])
        
        with patch("extractors.parse_pdf._parse_statement_year", return_value=2025):
            result = parse_pdf(Path("mock_statement.pdf"))
        
        self.assertEqual(len(result.records), 2)
        
        # Verify first record fields
        google_record = result.records[0]
        self.assertEqual(google_record.vendor, "GOOGLE *WORKSPACE")
        self.assertEqual(google_record.description, "TXN-99831")
        self.assertEqual(google_record.amount, 8.28)
        self.assertEqual(google_record.date, datetime.date(2025, 1, 5))
        self.assertEqual(google_record.payment_method, PaymentMethod.CREDIT_CARD)

    @patch("extractors.parse_pdf.pdfplumber.open")
    def test_parse_pdf_ignores_header_footer_and_summary_noise(self, mock_pdf_open) -> None:
        """Ensure that non-transaction layout lines, totals, and descriptors are filtered out."""
        simulated_text = """
        VISA BUSINESS CARD STATEMENT
        PREVIOUS BALANCE: $1,250.00
        
        TXN-99831 JAN 05 GOOGLE *WORKSPACE 8.28
        
        TOTAL FEES CHARGED THIS PERIOD: $0.00
        Page 1 of 1
        """
        mock_pdf_open.return_value = FakePdfDocument([FakePdfPage(simulated_text)])
        
        with patch("extractors.parse_pdf._parse_statement_year", return_value=2025):
            result = parse_pdf(Path("mock_noise.pdf"))
            
        # Only the line starting with TXN- should be captured
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].vendor, "GOOGLE *WORKSPACE")

    @patch("extractors.parse_pdf.pdfplumber.open")
    def test_parse_pdf_handles_negative_amounts_and_currency_symbols(self, mock_pdf_open) -> None:
        """Edge Case: Test that refunds or negative balances (prefixed with '-') are parsed successfully."""
        simulated_text = """
        STATEMENT YEAR 2025
        TXN-00002 FEB 10 MERCHANT REFUND -$50.00
        TXN-00003 FEB 11 CASHBACK CORRECTION -25.50
        """
        mock_pdf_open.return_value = FakePdfDocument([FakePdfPage(simulated_text)])
        
        with patch("extractors.parse_pdf._parse_statement_year", return_value=2025):
            result = parse_pdf(Path("mock_amounts.pdf"))
            
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.records[0].amount, -50.00)
        self.assertEqual(result.records[1].amount, -25.50)

    @patch("extractors.parse_pdf.pdfplumber.open")
    def test_parse_pdf_handles_multi_page_aggregation(self, mock_pdf_open) -> None:
        """Test that data splitting across page breaks compiles into a single flat array."""
        page_1 = FakePdfPage("TXN-101 JAN 05 GOOGLE *WORKSPACE 8.28")
        page_2 = FakePdfPage("TXN-102 FEB 06 ADOBE *CREATIVE CL 74.99")
        
        mock_pdf_open.return_value = FakePdfDocument([page_1, page_2])
        
        with patch("extractors.parse_pdf._parse_statement_year", return_value=2025):
            result = parse_pdf(Path("multi_page.pdf"))
            
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.records[0].vendor, "GOOGLE *WORKSPACE")
        self.assertEqual(result.records[1].vendor, "ADOBE *CREATIVE CL")

    @patch("extractors.parse_pdf.pdfplumber.open")
    def test_parse_pdf_missing_year_returns_none_dates(self, mock_pdf_open) -> None:
        """Edge Case: If the year parser fails to discover the statement context year, dates resolve safely to None."""
        simulated_text = "TXN-99831 JAN 05 GOOGLE *WORKSPACE 8.28"
        mock_pdf_open.return_value = FakePdfDocument([FakePdfPage(simulated_text)])
        
        # Explicitly simulate statement_year remaining None
        with patch("extractors.parse_pdf._parse_statement_year", return_value=None):
            result = parse_pdf(Path("no_year.pdf"))
            
        self.assertEqual(len(result.records), 1)
        self.assertIsNone(result.records[0].date)

    @patch("extractors.parse_pdf.pdfplumber.open")
    def test_parse_pdf_handles_malformed_month_strings(self, mock_pdf_open) -> None:
        """Edge Case: If a line matches regex but the month abbreviation is non-standard (e.g. ZZZ), date defaults to None."""
        simulated_text = "TXN-99831 ZZZ 05 GOOGLE *WORKSPACE 8.28"
        mock_pdf_open.return_value = FakePdfDocument([FakePdfPage(simulated_text)])
        
        # We modify the regex behavior locally via string injection to force regex match but date failure
        with patch("extractors.parse_pdf.TRANSACTION_LINE_PATTERN") as mock_pattern:
            mock_match = unittest.mock.MagicMock()
            mock_match.group.side_effect = lambda field: {
                "transaction_id": "TXN-99831",
                "month": "ZZZ",
                "day": "05",
                "description": "GOOGLE *WORKSPACE",
                "amount": "8.28"
            }[field]
            mock_pattern.match.return_value = mock_match
            
            with patch("extractors.parse_pdf._parse_statement_year", return_value=2025):
                result = parse_pdf(Path("bad_date.pdf"))
                
        self.assertEqual(len(result.records), 1)
        self.assertIsNone(result.records[0].date)


if __name__ == "__main__":
    unittest.main()