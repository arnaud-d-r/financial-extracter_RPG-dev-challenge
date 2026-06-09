from __future__ import annotations

import datetime
import json
from pathlib import Path

from extractors.models import AppDataBundle, TransactionCategory, Transaction, ExtractionResult, Warnings
from extractors.parse_images import parse_images
from extractors.parse_excel import parse_excel
from extractors.parse_pdf import parse_pdf


ROOT = Path(__file__).resolve().parent
SHOEBOX_DIR = ROOT / "shoebox"
OUTPUT_FILE = ROOT / "app_data.json"
NOTES_FILE = SHOEBOX_DIR / "notes.txt"



def infer_category_from_path(path: Path) -> TransactionCategory:
    name = path.name.lower()
    parent = path.parent.name.lower()

    if any(token in name for token in ("invoice", "invoices")):
        return TransactionCategory.INVOICE
    if any(token in name for token in ("statement", "bank", "visa", "credit")):
        return TransactionCategory.BANK_STATEMENT
    if   "receipt" in parent or "receipt" in name:
        return TransactionCategory.RECEIPT
    return TransactionCategory.UNKNOWN



def extract_file(path: Path) -> ExtractionResult:
    category = infer_category_from_path(path)
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return parse_excel(path, category=category)
    if suffix == ".pdf":
        return parse_pdf(path, category=category)
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return parse_images(path, category=category)
    return ExtractionResult(source_file=path.name, records=[])


def build_app_data(shoebox_dir: Path = SHOEBOX_DIR) -> AppDataBundle:
    records: list[Transaction] = []

    for path in sorted(shoebox_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("~$") or path.name == "notes.txt":
            continue

        extraction = extract_file(path)

        for record in extraction.records:
            records.append(record)

    return AppDataBundle( records=records)



def write_app_data( data: AppDataBundle, output_file: Path = OUTPUT_FILE) -> Path:
    output_file.write_text(json.dumps(data.to_dict(), indent=2), encoding="utf-8")


def read_app_data(input_file: Path = OUTPUT_FILE) -> AppDataBundle:
    return AppDataBundle.model_validate_json(input_file.read_text(encoding="utf-8"))

def patch_app_data(matching_trouple: tuple[str, datetime.date, float], warning_key: str) -> bool:
    data = read_app_data()
    matched = False
    warning = Warnings(warning_key)
    for record in data.records:
        if (
            record.source_file == matching_trouple[0]
            and record.date == matching_trouple[1]
            and record.amount == matching_trouple[2]
        ):
            matched = True
            if warning in record.warnings:
                record.warnings.remove(warning)
            else:
                return False
    if not matched:
        return False
    try:
        write_app_data(data=data)
    except Exception as e:
        print(f"Error writing app data: {e}")
        return False
    return True


def main() -> None:
    data=build_app_data()
    write_app_data(data=data)


if __name__ == "__main__":
    main()
