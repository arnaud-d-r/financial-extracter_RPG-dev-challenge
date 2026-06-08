from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

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
    def test_parse_pdf_splits_non_empty_lines_into_records(self) -> None:
        fake_pdfplumber = types.SimpleNamespace(
            open=lambda path: FakePdfDocument(
                [
                    FakePdfPage("Acme Studio\n\nSubscription"),
                    FakePdfPage("Blue Coffee"),
                ]
            )
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_file = Path(temp_dir) / "statement.pdf"
            pdf_file.write_bytes(b"placeholder")

            with patch.dict(sys.modules, {"pdfplumber": fake_pdfplumber}):
                result = parse_pdf(pdf_file)

        self.assertEqual(result.source_file, "statement.pdf")
        self.assertEqual([record.vendor for record in result.records], ["Acme Studio", "Subscription", "Blue Coffee"])
        self.assertEqual([record.metadata["page"] for record in result.records], [1, 1, 2])

    def test_parse_pdf_reads_real_statement(self) -> None:
        pdf_file = REPO_ROOT / "shoebox" / "Visa_Statement_Q12025.pdf"

        result = parse_pdf(pdf_file)

        vendors = [record.vendor for record in result.records]
        pages = {record.metadata["page"] for record in result.records}

        self.assertEqual(result.source_file, "Visa_Statement_Q12025.pdf")
        self.assertEqual(len(result.records), 50)
        self.assertIn("TXN-0110-001 Jan 10 NETFLIX.COM $16.99", vendors)
        self.assertIn("TXN-0106-001 Jan 06 ADOBE *CREATIVE CL $74.99", vendors)
        self.assertEqual(pages, {1, 2})


if __name__ == "__main__":
    unittest.main()
