from __future__ import annotations

from pathlib import Path

from .models import ExpenseRecord, ExtractionResult


def _normalise_row(row: object) -> dict[str, object]:
    return {str(key).strip().lower(): value for key, value in row.items()}


def _first_value(row: dict[str, object], names: tuple[str, ...]) -> object | None:
    for name in names:
        value = row.get(name)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _coerce_amount(value: object) -> float:
    if value is None:
        return 0.0

    if isinstance(value, str):
        cleaned = value.replace("$", "").replace(",", "").replace("–", "-").replace("−", "-").strip()
        if not cleaned:
            return 0.0
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_invoices(path: str | Path) -> ExtractionResult:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("pandas is required to parse invoice spreadsheets") from exc

    workbook = Path(path)
    frame = pd.read_excel(workbook)
    records: list[ExpenseRecord] = []

    for _, row in frame.iterrows():
        normalized_row = _normalise_row(row)
        vendor = str(_first_value(normalized_row, ("vendor", "merchant", "client", "payee")) or "Unknown")
        category = str(_first_value(normalized_row, ("category", "description", "memo", "details", "line item")) or "invoice")
        amount = _coerce_amount(_first_value(normalized_row, ("amount", "total", "value", "price")))
        date_value = _first_value(normalized_row, ("date", "date sent", "statement date", "date paid"))
        records.append(
            ExpenseRecord(
                source="invoice",
                date=str(date_value) if date_value is not None else None,
                vendor=vendor,
                category=category,
                amount=amount,
                metadata={"sheet": workbook.name},
            )
        )

    return ExtractionResult(source_file=workbook.name, records=records)
