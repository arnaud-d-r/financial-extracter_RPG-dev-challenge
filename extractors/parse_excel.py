from __future__ import annotations

from pathlib import Path
import datetime
from .models import ColumnMatching, TransactionCategory, Transaction, ExtractionResult, Warnings
import pandas as pd
from .utils import _coerce_amount, _first_value, _normalise_row, _parse_date, _is_empty


def parse_excel(path: str | Path, category: TransactionCategory) -> ExtractionResult:


    file_path = Path(path)
    frame = pd.read_excel(file_path)
    records: list[Transaction] = []

    for _, row in frame.iterrows():
        if hasattr(row, "dropna"):
            if row.dropna().empty:
                continue
        elif isinstance(row, dict):
            if all(_is_empty(v) for v in row.values()):
                continue
        
        normalized_row = _normalise_row(row)
        
        raw_vendor = _first_value(normalized_row, ColumnMatching["vendor"])
        raw_description = _first_value(normalized_row, ColumnMatching["description"])
        raw_amount = _first_value(normalized_row, ColumnMatching["amount"])
        raw_date = _first_value(normalized_row, ColumnMatching["date"])
        
        
        date_paid = None
        if category == TransactionCategory.INVOICE:
            date_paid = _first_value(normalized_row, ColumnMatching["invoice_paid_date"])


        vendor = str(raw_vendor).strip() if not _is_empty(raw_vendor) else None
        description = str(raw_description).strip() if not _is_empty(raw_description) else None
        
        amount = _coerce_amount(raw_amount) if not _is_empty(raw_amount) else None
        
        parsed_date = _parse_date(raw_date) if not _is_empty(raw_date) else None
        parsed_invoice_paid_date = _parse_date(date_paid) if (category == TransactionCategory.INVOICE and not _is_empty(date_paid)) else None

        try:
            records.append(
                Transaction(
                    source_file=file_path.name,
                    category=category,
                    vendor=vendor,
                    description=description,
                    date=parsed_date,
                    invoice_paid_date=parsed_invoice_paid_date,
                    amount=amount,
                    warnings=[],
                )
            )
        except Exception:
            continue

    return ExtractionResult(source_file=file_path.name, records=records)
