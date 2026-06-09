from __future__ import annotations

import datetime
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from extractors.models import TransactionCategory, PaymentMethod
from extractors.parse_images import parse_images, clean_and_validate_raw_output


class TestImageExtractorAndSanitization(unittest.TestCase):

    def setUp(self) -> None:
        """Set up standard text blocks mimicking unconstrained Qwen2-VL outputs."""
        self.mock_image_path = Path("shoebox/test_receipt.png")
        
        # 1. Clean happy path receipt (Mixed English/French)
        self.raw_happy_path_output = """
        ```json
        {
            "category": "receipt",
            "vendor": "Chen's Art Supply",
            "description": "Markers (x6)",
            "date": "03/08/2025",
            "total": "$27.50",
            "payment_method": "E-Transfer"
        }
        ```
        """
        
        # 2. Noise Image output (e.g. A picture of a cat instead of a receipt)
        self.raw_noise_output = """
        {
            "category": "unknown",
            "vendor": null,
            "description": null,
            "date": null,
            "total": null,
            "payment_method": null
        }
        """

    # ==============================================================================
    # 1. UNIT TESTS FOR DOWNSTREAM SANITIZATION & RE-MAPPING
    # ==============================================================================

    def test_clean_and_validate_happy_path(self) -> None:
        """Test sanitizing clean VLM markdown strings into complete Transaction schemas."""
        result = clean_and_validate_raw_output(self.raw_happy_path_output, "test_receipt.png")
        
        self.assertEqual(result.source_file, "test_receipt.png")
        self.assertEqual(result.category, TransactionCategory.RECEIPT)  # Maps string to Enum
        self.assertEqual(result.vendor, "Chen's Art Supply")
        self.assertEqual(result.amount, 27.50)  # Verify regex float coercion strips away '$'
        self.assertEqual(result.payment_method, PaymentMethod.E_TRANSFER)  # Maps string to Enum
        self.assertEqual(result.date, datetime.date(2025, 8, 3))  # Validates Day/Month ordering

    def test_clean_and_validate_french_payment_methods(self) -> None:
        """Edge Case: Ensure French localized terminology maps correctly to PaymentMethod enums."""
        french_cash_output = '{"category": "receipt", "total": "15.00", "payment_method": "comptant"}'
        french_card_output = '{"category": "receipt", "total": "45.10", "payment_method": " carte"}'
        
        tx_cash = clean_and_validate_raw_output(french_cash_output, "receipt.png")
        tx_card = clean_and_validate_raw_output(french_card_output, "receipt.png")
        
        self.assertEqual(tx_cash.payment_method, PaymentMethod.CASH)
        self.assertEqual(tx_card.payment_method, PaymentMethod.CREDIT_CARD)

    def test_clean_and_validate_handles_corrupted_json_gracefully(self) -> None:
        """Edge Case: If the model outputs completely malformed JSON, return a blank UNKNOWN record instead of crashing."""
        malformed_raw_str = "This is some random text block that isn't JSON at all."
        
        result = clean_and_validate_raw_output(malformed_raw_str, "corrupted.png")
        
        self.assertEqual(result.category, TransactionCategory.UNKNOWN)
        self.assertIsNone(result.vendor)
        self.assertIsNone(result.amount)
        self.assertIsNone(result.date)
        self.assertEqual(result.payment_method, PaymentMethod.UNKNOWN)

    def test_clean_and_validate_malformed_or_missing_date_formats(self) -> None:
        """Edge Case: Check that non-standard dates or strings with text components default smoothly to None."""
        bad_date_output = '{"category": "receipt", "date": "not-a-valid-date-string", "total": "10.00"}'
        
        result = clean_and_validate_raw_output(bad_date_output, "bad_date.png")
        self.assertIsNone(result.date)
        self.assertEqual(result.amount, 10.00)

    def test_clean_and_validate_handles_noise_images(self) -> None:
        """Edge Case: Check that noise data returns clean empty properties."""
        result = clean_and_validate_raw_output(self.raw_noise_output, "cat_meme.png")
        
        self.assertEqual(result.category, TransactionCategory.UNKNOWN)
        self.assertIsNone(result.vendor)
        self.assertIsNone(result.amount)
        self.assertIsNone(result.date)

    # ==============================================================================
    # 2. END-TO-END PIPELINE ORCHESTRATION INTEGRATION TESTS
    # ==============================================================================

    @patch("extractors.parse_images.Image.open")
    @patch("extractors.parse_images.tf_processor")
    @patch("extractors.parse_images.tf_model")
    def test_parse_images_full_pipeline_execution(self, mock_model, mock_processor, mock_image_open) -> None:
        """Test the end-to-end multi-modal pipeline execution up to packaging array data."""
        # 1. Mock context managers & PIL instances
        mock_img_instance = MagicMock()
        mock_image_open.return_value.__enter__.return_value = mock_img_instance

        # 2. Mock Transformers processor outputs
        mock_inputs = MagicMock()
        mock_inputs.input_ids = [[1, 2, 3]]
        mock_inputs.device = "cuda"
        mock_processor.return_value.to.return_value = mock_inputs

        # 3. Mock Model Generation IDs
        mock_model.device = "cuda"
        mock_model.generate.return_value = [[1, 2, 3, 4, 5, 6]]  # Prepends inputs

        # 4. Mock output decoder to emit a valid text string sequence
        mock_processor.batch_decode.return_value = [self.raw_happy_path_output]

        # Execute pipeline orchestrator
        result = parse_images(self.mock_image_path, category=TransactionCategory.RECEIPT)

        # Assert infrastructure bindings executed correctly
        mock_image_open.assert_called_once_with(self.mock_image_path)
        mock_model.generate.assert_called_once()
        
        # Verify returned data structural shapes match specs
        self.assertEqual(result.source_file, "test_receipt.png")
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].vendor, "Chen's Art Supply")
        self.assertEqual(result.records[0].amount, 27.50)
        
    def test_clean_and_validate_defends_against_null_category(self) -> None:
        """Edge Case: Ensure that a null or invalid string category value doesn't trigger an AttributeError."""
        null_category_json = '{"category": null, "vendor": "Test"}'
        result = clean_and_validate_raw_output(null_category_json, "edge_case.png")
        self.assertEqual(result.category, TransactionCategory.UNKNOWN)

    def test_clean_and_validate_defends_against_invalid_enum_string_category(self) -> None:
        """Edge Case: Ensure an invalid arbitrary category string safely defaults to UNKNOWN instead of an unhandled exception."""
        invalid_cat_json = '{"category": "unexpected_document_type", "vendor": "Test"}'
        result = clean_and_validate_raw_output(invalid_cat_json, "edge_case.png")
        self.assertEqual(result.category, TransactionCategory.UNKNOWN)

    def test_clean_and_validate_defends_against_empty_date_string(self) -> None:
        """Edge Case: Verify that blank or white-spaced date items do not throw unexpected IndexErrors on parsing."""
        empty_date_json = '{"category": "receipt", "date": "   ", "total": "12.50"}'
        result = clean_and_validate_raw_output(empty_date_json, "edge_case.png")
        self.assertIsNone(result.date)
        self.assertEqual(result.amount, 12.50)

    def test_clean_and_validate_defends_against_array_instead_of_dict(self) -> None:
        """Edge Case: Check that if the VLM returns an array block sequence instead of an object, it drops out smoothly."""
        array_json = '[{"category": "receipt", "total": "10.00"}]'
        result = clean_and_validate_raw_output(array_json, "edge_case.png")
        self.assertEqual(result.category, TransactionCategory.UNKNOWN)


if __name__ == "__main__":
    unittest.main()