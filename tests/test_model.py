import datetime
import unittest
from extractors.models import (
    Transaction,
    TransactionCategory,
    PaymentMethod,
    Warnings,
    ExtractionResult,
    AppDataBundle
)


class TestTransactionWarnings(unittest.TestCase):
    def setUp(self) -> None:
        """Set up a base valid transaction dictionary to mutate for tests."""
        self.today = datetime.date.today()
        self.past_date = self.today - datetime.timedelta(days=5)
        
        # A completely standard, valid receipt that triggers NO auto-warnings
        self.valid_receipt_base = {
            "source_file": "receipt.jpg",
            "category": TransactionCategory.RECEIPT,
            "vendor": "Valid Store",
            "description": "Office Supplies",
            "date": self.past_date,
            "amount": 42.50,
            "currency": "CAD",
            "invoice_paid_date": None,
            "payment_method": PaymentMethod.CASH,
            "warnings": []
        }

    def test_valid_transaction_no_warnings(self):
        """Ensure a completely clean record produces no unintended warning side-effects."""
        tx = Transaction(**self.valid_receipt_base)
        self.assertEqual(tx.warnings, [])

    def test_warning_invalid_vendor(self):
        """Trigger INVALID_VENDOR when missing, empty, or whitespace-only."""
        # Case 1: Empty string
        data_empty = self.valid_receipt_base.copy()
        data_empty["vendor"] = ""
        tx_empty = Transaction(**data_empty)
        self.assertIn(Warnings.INVALID_VENDOR, tx_empty.warnings)

        # Case 2: Whitespace only
        data_space = self.valid_receipt_base.copy()
        data_space["vendor"] = "   "
        tx_space = Transaction(**data_space)
        self.assertIn(Warnings.INVALID_VENDOR, tx_space.warnings)

        # Case 3: None
        data_none = self.valid_receipt_base.copy()
        data_none["vendor"] = None
        tx_none = Transaction(**data_none)
        self.assertIn(Warnings.INVALID_VENDOR, tx_none.warnings)

    def test_warning_invalid_amount(self):
        """Trigger INVALID_AMOUNT when amount is None."""
        data = self.valid_receipt_base.copy()
        data["amount"] = None
        tx = Transaction(**data)
        self.assertIn(Warnings.INVALID_AMOUNT, tx.warnings)

    def test_warning_negative_amount(self):
        """Trigger NEGATIVE_AMOUNT when value is strictly less than 0."""
        data = self.valid_receipt_base.copy()
        data["amount"] = -10.0
        tx = Transaction(**data)
        self.assertIn(Warnings.NEGATIVE_AMOUNT, tx.warnings)

    def test_warning_invalid_date(self):
        """Trigger INVALID_DATE when date is None."""
        data = self.valid_receipt_base.copy()
        data["date"] = None
        tx = Transaction(**data)
        self.assertIn(Warnings.INVALID_DATE, tx.warnings)

    def test_warning_future_date(self):
        """Trigger FUTURE_DATE if transaction date is tomorrow or further."""
        tomorrow = self.today + datetime.timedelta(days=1)
        data = self.valid_receipt_base.copy()
        data["date"] = tomorrow
        tx = Transaction(**data)
        self.assertIn(Warnings.FUTURE_DATE, tx.warnings)

    def test_warning_invalid_category(self):
        """Trigger INVALID_CATEGORY when document category type is UNKNOWN."""
        data = self.valid_receipt_base.copy()
        data["category"] = TransactionCategory.UNKNOWN
        tx = Transaction(**data)
        self.assertIn(Warnings.INVALID_CATEGORY, tx.warnings)

    def test_warning_invalid_invoice_paid_date(self):
        """Trigger INVALID_INVOICE_PAID_DATE if paid date exists but it is not an invoice."""
        data = self.valid_receipt_base.copy()
        data["category"] = TransactionCategory.RECEIPT
        data["invoice_paid_date"] = self.past_date
        tx = Transaction(**data)
        self.assertIn(Warnings.INVALID_INVOICE_PAID_DATE, tx.warnings)

    def test_warning_paid_before_sent(self):
        """Trigger PAID_BEFORE_SENT if an invoice payment date precedes the emission date."""
        data = self.valid_receipt_base.copy()
        data["category"] = TransactionCategory.INVOICE
        data["date"] = self.today  # Issued today
        data["invoice_paid_date"] = self.past_date  # "Paid" 5 days ago
        tx = Transaction(**data)
        self.assertIn(Warnings.PAID_BEFORE_SENT, tx.warnings)

    def test_warning_invoice_future_paid_date(self):
        """Trigger FUTURE_DATE if an invoice payment date is set in the future."""
        tomorrow = self.today + datetime.timedelta(days=1)
        data = self.valid_receipt_base.copy()
        data["category"] = TransactionCategory.INVOICE
        data["date"] = self.past_date
        data["invoice_paid_date"] = tomorrow
        tx = Transaction(**data)
        self.assertIn(Warnings.FUTURE_DATE, tx.warnings)

    def test_warning_unpaid_invoice(self):
        """Trigger UNPAID_INVOICE if document is an invoice but missing invoice_paid_date."""
        data = self.valid_receipt_base.copy()
        data["category"] = TransactionCategory.INVOICE
        data["invoice_paid_date"] = None
        tx = Transaction(**data)
        self.assertIn(Warnings.UNPAID_INVOICE, tx.warnings)

    def test_warning_not_cash_receipt(self):
        """Trigger NOT_CASH_RECEIPT if document is a receipt but paid with alternative methods."""
        data = self.valid_receipt_base.copy()
        data["category"] = TransactionCategory.RECEIPT
        data["payment_method"] = PaymentMethod.CREDIT_CARD
        tx = Transaction(**data)
        self.assertIn(Warnings.NOT_CASH_RECEIPT, tx.warnings)

    def test_deduplication_of_manually_passed_warnings(self):
        """Ensure that warnings manually passed in are safely deduplicated alongside generated ones."""
        data = self.valid_receipt_base.copy()
        data["amount"] = -50.0  # Will trigger Warnings.NEGATIVE_AMOUNT internally
        data["warnings"] = [Warnings.NEGATIVE_AMOUNT, Warnings.PERSONAL_EXPENSE]
        
        tx = Transaction(**data)
        # Count occurrences of NEGATIVE_AMOUNT to check uniqueness constraint
        negative_amount_count = tx.warnings.count(Warnings.NEGATIVE_AMOUNT)
        self.assertEqual(negative_amount_count, 1)
        self.assertIn(Warnings.PERSONAL_EXPENSE, tx.warnings)


class TestContainerModels(unittest.TestCase):
    """Verifies that parent wrapper classes enforce serialization rules properly."""

    def test_extraction_result_json_serialization(self):
        tx_data = {
            "source_file": "test.png",
            "category": TransactionCategory.BANK_STATEMENT,
            "vendor": "Bank",
            "amount": 100.0,
            "date": datetime.date(2026, 1, 1),
            "payment_method": PaymentMethod.UNKNOWN
        }
        tx = Transaction(**tx_data)
        result = ExtractionResult(source_file="test.png", records=[tx])
        
        dictionary_output = result.to_dict()
        self.assertIsInstance(dictionary_output, dict)
        self.assertEqual(dictionary_output["source_file"], "test.png")
        self.assertEqual(dictionary_output["records"][0]["amount"], 100.0)

    def test_app_data_bundle_serialization(self):
        tx = Transaction(
            source_file="statement.pdf",
            category=TransactionCategory.BANK_STATEMENT,
            vendor="Telecom",
            amount=55.0,
            date=datetime.date(2026, 2, 2)
        )
        bundle = AppDataBundle(records=[tx])
        dictionary_output = bundle.to_dict()
        self.assertIn("records", dictionary_output)
        self.assertEqual(len(dictionary_output["records"]), 1)


if __name__ == "__main__":
    unittest.main()