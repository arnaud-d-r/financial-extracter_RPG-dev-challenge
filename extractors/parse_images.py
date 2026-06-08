from __future__ import annotations

from pathlib import Path

from .models import  Transaction, ExtractionResult, TransactionCategory


def parse_images(path: str | Path, category: TransactionCategory = TransactionCategory.RECEIPT) -> ExtractionResult:
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
            Transaction(
                source_file=image_path.name,
                category=category,
                vendor=image_path.stem,
                description=image_path.name,
                date=None,
                amount=None,
                warnings=[],
            )
        ]
    )
