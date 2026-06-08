from __future__ import annotations

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

PERSONAL_KEYWORDS = {
    "personal",
    "bussiness card",
}


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


def load_personal_exclusions(notes_path: Path = NOTES_FILE) -> set[str]:
    if not notes_path.exists():
        return set()

    clues: set[str] = set()
    for raw_line in notes_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip().lower()
        if not line or line.startswith("["):
            continue
        for keyword in PERSONAL_KEYWORDS:
            if keyword in line:
                clues.add(keyword)
    return clues


def is_personal_expense(record: Transaction, personal_clues: set[str]) -> bool:
    haystack = f"{record.vendor or ''} {record.description or ''} {record.category.value}".lower()
    return any(clue in haystack for clue in personal_clues)


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
    personal_clues = load_personal_exclusions(shoebox_dir / "notes.txt")
    records: list[Transaction] = []

    for path in sorted(shoebox_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("~$") or path.name == "notes.txt":
            continue

        extraction = extract_file(path)

        for record in extraction.records:
            if is_personal_expense(record, personal_clues):
                record.warnings.append(Warnings.PERSONAL_EXPENSE)
            records.append(record)

    return AppDataBundle(source_folder=str(shoebox_dir), records=records)



def write_app_data(output_file: Path = OUTPUT_FILE, shoebox_dir: Path = SHOEBOX_DIR) -> Path:
    payload = build_app_data(shoebox_dir)
    output_file.write_text(json.dumps(payload.to_dict(), indent=2), encoding="utf-8")
    return output_file


def read_app_data(input_file: Path = OUTPUT_FILE) -> AppDataBundle:
    return AppDataBundle.model_validate_json(input_file.read_text(encoding="utf-8"))


def main() -> None:
    write_app_data()


if __name__ == "__main__":
    main()
