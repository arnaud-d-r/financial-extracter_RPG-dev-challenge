from __future__ import annotations

from pathlib import Path
import datetime
from .models import ColumnMatching, TransactionCategory, Transaction, ExtractionResult, Warnings
import pandas as pd
from .utils import _coerce_amount, _first_value, _normalise_row, _parse_date


def parse_excel(path: str | Path, category: TransactionCategory) -> ExtractionResult:


    file_path = Path(path)
    frame = pd.read_excel(file_path)
    records: list[Transaction] = []

    for _, row in frame.iterrows():
        normalized_row = _normalise_row(row)
        vendor = _first_value(normalized_row, ColumnMatching["vendor"])
        description = _first_value(normalized_row, ColumnMatching["description"])
        amount = _coerce_amount(_first_value(normalized_row, ColumnMatching["amount"]))
        date_value = _first_value(normalized_row, ColumnMatching["date"])
        if category == TransactionCategory.INVOICE :
            date_paid = _first_value(normalized_row, ColumnMatching["invoice_paid_date"])



        records.append(
            Transaction(
                source_file=file_path.name,
                category=category,
                vendor=str(vendor) if vendor is not None else None,
                description=str(description) if description is not None else None,
                date=_parse_date(date_value),
                invoice_paid_date=_parse_date(date_paid) if category == TransactionCategory.INVOICE else None,
                amount=amount,
                warnings=[],
            )
        )

    return ExtractionResult(source_file=file_path.name, records=records)
