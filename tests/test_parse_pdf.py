from __future__ import annotations

import datetime
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from extractors.models import TransactionCategory
from extractors.parse_pdf import parse_pdf


REPO_ROOT = Path(__file__).resolve().parents[1]


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

    def test_parse_pdf_reads_real_statement(self) -> None:
        pdf_file = REPO_ROOT / "shoebox" / "Visa_Statement_Q12025.pdf"

        result = parse_pdf(pdf_file)

        self.assertEqual(result.source_file, "Visa_Statement_Q12025.pdf")
        self.assertEqual(len(result.records), 36)
        self.assertEqual(result.records[0].category, TransactionCategory.BANK_STATEMENT)
        self.assertTrue(any(record.vendor == "GOOGLE *WORKSPACE" and record.amount == 8.28 for record in result.records))
        self.assertTrue(any(record.vendor == "ADOBE *CREATIVE CL" and record.amount == 74.99 and record.date == datetime.date(2025, 2, 6) for record in result.records))


if __name__ == "__main__":
    unittest.main()
