from __future__ import annotations

import json
from pathlib import Path

from extractors.models import ExpenseRecord, ExtractionResult
from extractors.parse_images import parse_images
from extractors.parse_invoices import parse_invoices
from extractors.parse_pdf import parse_pdf


ROOT = Path(__file__).resolve().parent
SHOEBOX_DIR = ROOT / "shoebox"
OUTPUT_FILE = ROOT / "app_data.json"
NOTES_FILE = SHOEBOX_DIR / "notes.txt"

PERSONAL_KEYWORDS = {
    "personal",
    "netflix",
    "dog food",
    "pharmacy",
    "home office",
}


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


def is_personal_expense(record: ExpenseRecord, personal_clues: set[str]) -> bool:
    haystack = f"{record.vendor} {record.category} {record.source}".lower()
    return any(clue in haystack for clue in personal_clues)


def extract_file(path: Path) -> ExtractionResult:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return parse_invoices(path)
    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return parse_images(path)
    return ExtractionResult(source_file=path.name, records=[], warnings=["Unsupported file type"])


def build_app_data(shoebox_dir: Path = SHOEBOX_DIR) -> dict:
    personal_clues = load_personal_exclusions(shoebox_dir / "notes.txt")
    items: list[dict] = []
    warnings: list[str] = []

    for path in sorted(shoebox_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("~$") or path.name == "notes.txt":
            continue

        extraction = extract_file(path)
        warnings.extend(extraction.warnings)

        for record in extraction.records:
            if is_personal_expense(record, personal_clues):
                continue
            items.append(record.to_dict())

    return {
        "source_folder": str(shoebox_dir),
        "records": items,
        "warnings": warnings,
    }


def generate_app_data(shoebox_dir: Path = SHOEBOX_DIR) -> dict:
    return build_app_data(shoebox_dir)


def write_app_data(output_file: Path = OUTPUT_FILE, shoebox_dir: Path = SHOEBOX_DIR) -> Path:
    payload = generate_app_data(shoebox_dir)
    output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_file


def read_app_data(input_file: Path = OUTPUT_FILE) -> dict:
    return json.loads(input_file.read_text(encoding="utf-8"))


def main() -> None:
    write_app_data()


if __name__ == "__main__":
    main()
