from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
import datetime


class TransactionCategory(Enum):
    INVOICE = "invoice"
    BANK_STATEMENT = "bank_statement"
    RECEIPT = "receipt"
    UNKNOWN = "unknown"
    
    
ColumnMatching: dict[str, list[str]] = {
    "vendor": ("vendor", "merchant", "client"),
    "description": ("description", "details", "line item"),
    "amount": ("amount", "total", "value", "price"),
    "date": ("date", "date sent", "statement date"),
    "invoice_paid_date": ("date paid", "payment date", "paid date")
}
    
class PaymentMethod(Enum):
    CREDIT_CARD = "credit_card"
    CASH = "cash"
    E_TRANSFER = "electronic_transfer"
    UNKNOWN = "unknown"
    
class Warnings(Enum):
    INVALID_AMOUNT = "invalid_amount"
    INVALID_VENDOR = "invalid_vendor"
    INVALID_DATE = "invalid_date"
    INVALID_CATEGORY = "invalid_category"
    INVALID_INVOICE_PAID_DATE = "invalid_invoice_paid_date"
    FUTURE_DATE = "future_date"
    PAID_BEFORE_SENT = "paid_before_sent"
    PERSONAL_EXPENSE = "personal_expense"
    UNPAID_INVOICE = "unpaid_invoice"
    NOT_CASH_RECEIPT = "not_cash_receipt"
    NEGATIVE_AMOUNT = "negative_amount"

class Transaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_file: str
    category: TransactionCategory
    vendor: str | None = None
    description: str | None = None
    date: datetime.date | None = None
    amount: float | None = None
    currency: str = "CAD"
    invoice_paid_date: datetime.date | None = None
    payment_method: PaymentMethod | None = None
    warnings: list[Warnings] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_record(self) -> "Transaction":
        issues = list(dict.fromkeys(self.warnings))

        if not self.vendor or not self.vendor.strip():
            issues.append(Warnings.INVALID_VENDOR)
        if self.amount is None:
            issues.append(Warnings.INVALID_AMOUNT)
        elif self.amount < 0:
            issues.append(Warnings.NEGATIVE_AMOUNT)
        if self.date is None:
            issues.append(Warnings.INVALID_DATE)
        elif self.date > datetime.date.today():
            issues.append(Warnings.FUTURE_DATE)
        if self.category == TransactionCategory.UNKNOWN:
            issues.append(Warnings.INVALID_CATEGORY)
        if self.category != TransactionCategory.INVOICE:
            if self.invoice_paid_date:
                issues.append(Warnings.INVALID_INVOICE_PAID_DATE)
        else:
            if self.invoice_paid_date and self.date:
                if self.invoice_paid_date < self.date:
                    issues.append(Warnings.PAID_BEFORE_SENT)
                if self.invoice_paid_date > datetime.date.today():
                    issues.append(Warnings.FUTURE_DATE) 
            if not self.invoice_paid_date:
                issues.append(Warnings.UNPAID_INVOICE)
        if self.category == TransactionCategory.RECEIPT and self.payment_method != PaymentMethod.CASH:
            issues.append(Warnings.NOT_CASH_RECEIPT)

        self.warnings = list(dict.fromkeys(issues))
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_file: str
    records: list[Transaction]

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class AppDataBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[Transaction]
    warnings: list[Warnings] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


