from __future__ import annotations

from pathlib import Path

from .models import ExpenseRecord, ExtractionResult


def parse_pdf(path: str | Path) -> ExtractionResult:
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required to parse text-based PDFs") from exc

    pdf_path = Path(path)
    records: list[ExpenseRecord] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            for line in text.splitlines():
                if not line.strip():
                    continue
                records.append(
                    ExpenseRecord(
                        source="pdf",
                        date=None,
                        vendor=line.strip(),
                        category="statement-line",
                        amount=0.0,
                        metadata={"page": page_number},
                    )
                )

    return ExtractionResult(source_file=pdf_path.name, records=records)
