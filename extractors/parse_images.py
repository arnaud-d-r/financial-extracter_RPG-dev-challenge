from __future__ import annotations

from pathlib import Path

from .models import ExpenseRecord, ExtractionResult


def parse_images(path: str | Path) -> ExtractionResult:
    image_path = Path(path)
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required to parse receipt images") from exc

    with Image.open(image_path) as image:
        metadata = {"size": image.size, "mode": image.mode}

    return ExtractionResult(
        source_file=image_path.name,
        records=[
            ExpenseRecord(
                source="image",
                date=None,
                vendor=image_path.stem,
                category="receipt",
                amount=0.0,
                metadata=metadata,
            )
        ],
        warnings=["OCR/vLLM integration not wired yet"],
    )
