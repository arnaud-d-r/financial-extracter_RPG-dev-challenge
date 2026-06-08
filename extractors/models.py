from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ExpenseRecord:
    source: str
    date: str | None
    vendor: str
    category: str
    amount: float
    currency: str = "CAD"
    is_personal: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExtractionResult:
    source_file: str
    records: list[ExpenseRecord]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "records": [record.to_dict() for record in self.records],
            "warnings": list(self.warnings),
        }
