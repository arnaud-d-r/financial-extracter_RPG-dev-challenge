from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main
from extractors.models import ExpenseRecord, ExtractionResult


class MainPipelineTests(unittest.TestCase):
    def test_generate_app_data_filters_personal_expenses(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            shoebox_dir = Path(temp_dir)
            (shoebox_dir / "notes.txt").write_text("netflix should be personal\n", encoding="utf-8")
            (shoebox_dir / "invoice.xlsx").write_text("placeholder", encoding="utf-8")

            def fake_extract_file(path: Path) -> ExtractionResult:
                if path.name == "invoice.xlsx":
                    return ExtractionResult(
                        source_file=path.name,
                        records=[
                            ExpenseRecord(
                                source="invoice",
                                date=None,
                                vendor="Netflix",
                                category="subscription",
                                amount=10.0,
                            ),
                            ExpenseRecord(
                                source="invoice",
                                date=None,
                                vendor="Acme Studio",
                                category="business",
                                amount=99.0,
                            ),
                        ],
                    )
                return ExtractionResult(source_file=path.name, records=[])

            with patch.object(main, "extract_file", side_effect=fake_extract_file):
                payload = main.generate_app_data(shoebox_dir)

        self.assertEqual(len(payload["records"]), 1)
        self.assertEqual(payload["records"][0]["vendor"], "Acme Studio")

    def test_write_and_read_app_data_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "app_data.json"
            shoebox_dir = Path(temp_dir) / "shoebox"
            shoebox_dir.mkdir()

            with patch.object(main, "generate_app_data", return_value={"records": [], "warnings": []}) as generate_mock:
                written_file = main.write_app_data(output_file, shoebox_dir)

            self.assertEqual(written_file, output_file)
            self.assertTrue(output_file.exists())
            self.assertEqual(main.read_app_data(output_file), {"records": [], "warnings": []})
            generate_mock.assert_called_once_with(shoebox_dir)


if __name__ == "__main__":
    unittest.main()