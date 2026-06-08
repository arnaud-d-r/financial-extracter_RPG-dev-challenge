from __future__ import annotations

import datetime
import re
from pathlib import Path

from .models import ExtractionResult, Transaction, TransactionCategory, Warnings
from .utils import _coerce_amount, _normalise_line, _parse_statement_year

import pdfplumber

TRANSACTION_LINE_PATTERN = re.compile(
    r"^(?P<transaction_id>TXN-[^\s]+)\s+(?P<month>[A-Za-z]{3})\s+(?P<day>\d{2})\s+(?P<description>.+?)\s+(?P<amount>-?\$?[\d.,]+)$"
)


def _parse_transaction_date(month: str, day: str, year: int | None) -> datetime.date | None:
    if year is None:
        return None

    try:
        return datetime.datetime.strptime(f"{month} {day} {year}", "%b %d %Y").date()
    except ValueError:
        return None


def parse_pdf(
    path: str | Path,
    category: TransactionCategory = TransactionCategory.BANK_STATEMENT,
) -> ExtractionResult:
    

    pdf_path = Path(path)
    records: list[Transaction] = []
    statement_year: int | None = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                normalised = _normalise_line(line)
                if not normalised:
                    continue

                if statement_year is None:
                    statement_year = _parse_statement_year(normalised)

                match = TRANSACTION_LINE_PATTERN.match(normalised)
                if not match:
                    continue

                records.append(
                    Transaction(
                        source_file=pdf_path.name,
                        category=category,
                        vendor=match.group("description").strip(),
                        description=match.group("transaction_id"),
                        date=_parse_transaction_date(
                            match.group("month"), match.group("day"), statement_year
                        ),
                        amount=_coerce_amount(match.group("amount")),
                        warnings=[],
                    )
                )

    return ExtractionResult(source_file=pdf_path.name, records=records)

