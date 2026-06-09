import datetime
from pathlib import Path
import re
from typing import Any
import pandas as pd

YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")

def _normalise_line(line: str) -> str:
    return line.strip().replace("\u2013", "-").replace("\u2212", "-").replace("–", "-").replace("−", "-")

def _parse_statement_year(line: str) -> int | None:
    match = YEAR_PATTERN.search(line)
    return int(match.group(0)) if match else None

def _is_empty(val : Any) -> bool:
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):  
        return True
    if pd.isna(val): 
        return True
    return False

def _normalise_row(row: object) -> dict[str, object]:
    return {str(key).strip().lower(): value for key, value in row.items()}


def _first_value(row: dict[str, object], names: list[str]) -> object | None:
    for name in names:
        value = row.get(name)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _coerce_amount(value: object) -> float | None:
    if value is None:
        return None

    if isinstance(value, str):
        cleaned = (
            value.replace("$", "").replace(",", "")
                 .replace("–", "-").replace("−", "-")
                 .strip()
        )
        if not cleaned:
            return None
        
        # Handle accounting-style negatives: (123.45) → -123.45
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = f"-{cleaned[1:-1]}"
        try:
            return float(cleaned)
        except ValueError:
            return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _parse_date(value: object) -> datetime.date | None:
    if value is None or pd.isna(value):
        return None

    if isinstance(value, datetime.datetime):
        return value.date()

    if isinstance(value, datetime.date):
        return value

    try:
        dt = pd.to_datetime(value, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.date()
    except Exception:
        return None
