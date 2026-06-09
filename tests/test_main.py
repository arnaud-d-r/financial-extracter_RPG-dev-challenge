from __future__ import annotations

import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import main
from extractors.models import (
    AppDataBundle,
    ExtractionResult,
    Transaction,
    TransactionCategory,
    Warnings,
)


# ─── Factories ────────────────────────────────────────────────────────────────


def make_transaction(**kwargs) -> Transaction:
    """Minimal valid Transaction; override any field via kwargs."""
    defaults = dict(
        source_file="statement.pdf",
        category=TransactionCategory.BANK_STATEMENT,
        vendor="Acme Corp",
        date=datetime.date(2025, 1, 15),
        amount=100.0,
    )
    return Transaction(**{**defaults, **kwargs})


def make_bundle(*records: Transaction, warnings=None) -> AppDataBundle:
    return AppDataBundle(records=list(records))


# ─── infer_category_from_path ─────────────────────────────────────────────────


class InferCategoryTests(unittest.TestCase):

    def test_invoice_by_filename(self):
        self.assertEqual(
            main.infer_category_from_path(Path("invoices.xlsx")),
            TransactionCategory.INVOICE,
        )

    def test_invoice_singular(self):
        self.assertEqual(
            main.infer_category_from_path(Path("invoice_jan.xlsx")),
            TransactionCategory.INVOICE,
        )

    def test_bank_statement_by_filename(self):
        for name in ("statement.pdf", "bank_export.pdf", "visa_march.pdf", "credit_card.pdf"):
            with self.subTest(name=name):
                self.assertEqual(
                    main.infer_category_from_path(Path(name)),
                    TransactionCategory.BANK_STATEMENT,
                )

    def test_receipt_by_parent_directory(self):
        self.assertEqual(
            main.infer_category_from_path(Path("receipts/scan_01.jpg")),
            TransactionCategory.RECEIPT,
        )

    def test_receipt_by_filename(self):
        self.assertEqual(
            main.infer_category_from_path(Path("receipt_coffee.jpg")),
            TransactionCategory.RECEIPT,
        )

    def test_unknown_fallback(self):
        self.assertEqual(
            main.infer_category_from_path(Path("random_file.txt")),
            TransactionCategory.UNKNOWN,
        )


# ─── extract_file ─────────────────────────────────────────────────────────────


class ExtractFileTests(unittest.TestCase):

    def _empty_result(self, path):
        return ExtractionResult(source_file=path.name, records=[])

    def test_dispatches_xlsx_to_parse_excel(self):
        path = Path("invoices.xlsx")
        with patch("main.parse_excel", return_value=self._empty_result(path)) as mock:
            main.extract_file(path)
        mock.assert_called_once_with(path, category=TransactionCategory.INVOICE)

    def test_dispatches_pdf_to_parse_pdf(self):
        path = Path("statement.pdf")
        with patch("main.parse_pdf", return_value=self._empty_result(path)) as mock:
            main.extract_file(path)
        mock.assert_called_once_with(path, category=TransactionCategory.BANK_STATEMENT)

    def test_dispatches_jpg_to_parse_images(self):
        path = Path("receipts/scan.jpg")
        with patch("main.parse_images", return_value=self._empty_result(path)) as mock:
            main.extract_file(path)
        mock.assert_called_once_with(path, category=TransactionCategory.RECEIPT)

    def test_dispatches_png_to_parse_images(self):
        path = Path("receipts/scan.png")
        with patch("main.parse_images", return_value=self._empty_result(path)) as mock:
            main.extract_file(path)
        mock.assert_called_once()

    def test_dispatches_webp_to_parse_images(self):
        path = Path("receipts/scan.webp")
        with patch("main.parse_images", return_value=self._empty_result(path)) as mock:
            main.extract_file(path)
        mock.assert_called_once()

    def test_unknown_extension_returns_empty_result(self):
        path = Path("notes.md")
        result = main.extract_file(path)
        self.assertIsInstance(result, ExtractionResult)
        self.assertEqual(result.records, [])


# ─── build_app_data ───────────────────────────────────────────────────────────


class BuildAppDataTests(unittest.TestCase):

    def test_collects_records_from_all_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            shoebox = Path(tmp)
            (shoebox / "invoices.xlsx").write_bytes(b"placeholder")
            (shoebox / "statement.pdf").write_bytes(b"placeholder")

            r1 = make_transaction(source_file="invoices.xlsx", category=TransactionCategory.INVOICE)
            r2 = make_transaction(source_file="statement.pdf")

            def fake_extract(path: Path) -> ExtractionResult:
                if path.name == "invoices.xlsx":
                    return ExtractionResult(source_file=path.name, records=[r1])
                if path.name == "statement.pdf":
                    return ExtractionResult(source_file=path.name, records=[r2])
                return ExtractionResult(source_file=path.name, records=[])

            with patch.object(main, "extract_file", side_effect=fake_extract):
                bundle = main.build_app_data(shoebox)

        self.assertIsInstance(bundle, AppDataBundle)
        self.assertEqual(len(bundle.records), 2)

    def test_skips_notes_txt(self):
        with tempfile.TemporaryDirectory() as tmp:
            shoebox = Path(tmp)
            (shoebox / "notes.txt").write_text("netflix should be personal\n")

            with patch.object(main, "extract_file") as mock_extract:
                main.build_app_data(shoebox)

            called_names = [c.args[0].name for c in mock_extract.call_args_list]
            self.assertNotIn("notes.txt", called_names)

    def test_skips_temp_excel_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            shoebox = Path(tmp)
            (shoebox / "~$invoices.xlsx").write_bytes(b"lock")

            with patch.object(main, "extract_file") as mock_extract:
                main.build_app_data(shoebox)

            called_names = [c.args[0].name for c in mock_extract.call_args_list]
            self.assertNotIn("~$invoices.xlsx", called_names)

    def test_skips_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            shoebox = Path(tmp)
            (shoebox / "receipts").mkdir()

            with patch.object(main, "extract_file") as mock_extract:
                main.build_app_data(shoebox)

            # Only files should have been passed to extract_file
            for c in mock_extract.call_args_list:
                self.assertTrue(c.args[0].is_file())

    def test_empty_shoebox_returns_empty_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = main.build_app_data(Path(tmp))
        self.assertEqual(bundle.records, [])



# ─── write_app_data / read_app_data ──────────────────────────────────────────


class ReadWriteAppDataTests(unittest.TestCase):

    def test_round_trip_empty_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "app_data.json"
            bundle = make_bundle()
            main.write_app_data(data=bundle, output_file=output)
            result = main.read_app_data(output)
        self.assertEqual(result, bundle)

    def test_round_trip_with_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "app_data.json"
            record = make_transaction()
            bundle = make_bundle(record)
            main.write_app_data(data=bundle, output_file=output)
            result = main.read_app_data(output)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].source_file, "statement.pdf")
        self.assertEqual(result.records[0].amount, 100.0)

    def test_write_creates_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "app_data.json"
            main.write_app_data(data=make_bundle(), output_file=output)
            parsed = json.loads(output.read_text())
        self.assertIn("records", parsed)

    def test_write_and_read_preserves_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "app_data.json"
            record = make_transaction(vendor=None, date=None)
            bundle = make_bundle(record)
            main.write_app_data(data=bundle, output_file=output)
            result = main.read_app_data(output)
        self.assertIn(Warnings.INVALID_VENDOR, result.records[0].warnings)
        self.assertIn(Warnings.INVALID_DATE, result.records[0].warnings)

    def test_write_uses_default_output_path(self):
        bundle = make_bundle()
        mock_path = MagicMock(spec=Path)
        with patch.object(main, "OUTPUT_FILE", mock_path):
            main.write_app_data(data=bundle, output_file=main.OUTPUT_FILE)
        mock_path.write_text.assert_called_once()


# ─── patch_app_data ───────────────────────────────────────────────────────────


class PatchAppDataTests(unittest.TestCase):

    MATCH = ("statement.pdf", datetime.date(2025, 1, 15), 100.0)

    def _run(self, bundle: AppDataBundle, warning: Warnings) -> bool:
        with patch.object(main, "read_app_data", return_value=bundle), \
             patch.object(main, "write_app_data"):
            return main.patch_app_data(self.MATCH, warning.value)

    def _run_capture_write(self, bundle: AppDataBundle, warning: Warnings):
        mock_write = MagicMock()
        with patch.object(main, "read_app_data", return_value=bundle), \
             patch.object(main, "write_app_data", mock_write):
            result = main.patch_app_data(self.MATCH, warning.value)
        return result, mock_write

    # Happy path

    def test_removes_warning_and_returns_true(self):
        record = make_transaction()
        record.warnings = [Warnings.NEGATIVE_AMOUNT]
        result = self._run(make_bundle(record), Warnings.NEGATIVE_AMOUNT)
        self.assertTrue(result)
        self.assertNotIn(Warnings.NEGATIVE_AMOUNT, record.warnings)

    def test_write_is_called_on_success(self):
        record = make_transaction()
        record.warnings = [Warnings.NEGATIVE_AMOUNT]
        _, mock_write = self._run_capture_write(make_bundle(record), Warnings.NEGATIVE_AMOUNT)
        mock_write.assert_called_once()

    def test_removes_targeted_warning_leaves_others(self):
        record = make_transaction()
        record.warnings = [Warnings.NEGATIVE_AMOUNT, Warnings.INVALID_VENDOR]
        self._run(make_bundle(record), Warnings.NEGATIVE_AMOUNT)
        self.assertNotIn(Warnings.NEGATIVE_AMOUNT, record.warnings)
        self.assertIn(Warnings.INVALID_VENDOR, record.warnings)

    def test_patches_all_records_sharing_same_key(self):
        """Both records with identical key are patched (loop runs to completion)."""
        r1 = make_transaction()
        r1.warnings = [Warnings.NEGATIVE_AMOUNT]
        r2 = make_transaction()
        r2.warnings = [Warnings.NEGATIVE_AMOUNT]
        self._run(make_bundle(r1, r2), Warnings.NEGATIVE_AMOUNT)
        self.assertNotIn(Warnings.NEGATIVE_AMOUNT, r1.warnings)
        self.assertNotIn(Warnings.NEGATIVE_AMOUNT, r2.warnings)

    # No match on record fields

    def test_returns_false_when_no_record_matches(self):
        record = make_transaction(source_file="other.pdf")
        record.warnings = [Warnings.NEGATIVE_AMOUNT]
        result = self._run(make_bundle(record), Warnings.NEGATIVE_AMOUNT)
        self.assertFalse(result)

    def test_returns_false_on_date_mismatch(self):
        record = make_transaction(date=datetime.date(2025, 3, 1))
        record.warnings = [Warnings.NEGATIVE_AMOUNT]
        result = self._run(make_bundle(record), Warnings.NEGATIVE_AMOUNT)
        self.assertFalse(result)

    def test_returns_false_on_amount_mismatch(self):
        record = make_transaction(amount=999.0)
        record.warnings = [Warnings.NEGATIVE_AMOUNT]
        result = self._run(make_bundle(record), Warnings.NEGATIVE_AMOUNT)
        self.assertFalse(result)

    def test_write_not_called_when_no_record_matches(self):
        record = make_transaction(source_file="other.pdf")
        record.warnings = [Warnings.NEGATIVE_AMOUNT]
        _, mock_write = self._run_capture_write(make_bundle(record), Warnings.NEGATIVE_AMOUNT)
        mock_write.assert_not_called()

    # Warning absent on matched record

    def test_returns_false_when_warning_absent_on_matched_record(self):
        record = make_transaction()
        record.warnings = []
        result = self._run(make_bundle(record), Warnings.NEGATIVE_AMOUNT)
        self.assertFalse(result)

    def test_write_not_called_when_warning_absent(self):
        record = make_transaction()
        record.warnings = []
        _, mock_write = self._run_capture_write(make_bundle(record), Warnings.NEGATIVE_AMOUNT)
        mock_write.assert_not_called()

    # Edge cases

    def test_empty_bundle_returns_false(self):
        result = self._run(make_bundle(), Warnings.NEGATIVE_AMOUNT)
        self.assertFalse(result)

    def test_returns_false_when_write_raises(self):
        record = make_transaction()
        record.warnings = [Warnings.NEGATIVE_AMOUNT]
        bundle = make_bundle(record)
        with patch.object(main, "read_app_data", return_value=bundle), \
             patch.object(main, "write_app_data", side_effect=OSError("disk full")):
            result = main.patch_app_data(self.MATCH, Warnings.NEGATIVE_AMOUNT.value)
        self.assertFalse(result)

    def test_invalid_warning_key_raises_value_error(self):
        """An unrecognised warning string should raise before touching any data."""
        record = make_transaction()
        bundle = make_bundle(record)
        with patch.object(main, "read_app_data", return_value=bundle), \
             patch.object(main, "write_app_data"):
            with self.assertRaises(ValueError):
                main.patch_app_data(self.MATCH, "not_a_real_warning")


# ─── main() ───────────────────────────────────────────────────────────────────


class MainEntrypointTests(unittest.TestCase):

    def test_main_calls_build_and_write(self):
        bundle = make_bundle()
        with patch.object(main, "build_app_data", return_value=bundle) as mock_build, \
             patch.object(main, "write_app_data") as mock_write:
            main.main()
        mock_build.assert_called_once()
        mock_write.assert_called_once_with(data=bundle)


if __name__ == "__main__":
    unittest.main()