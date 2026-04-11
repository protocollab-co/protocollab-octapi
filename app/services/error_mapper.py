from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NormalizedValidationError(Exception):
    field: str
    message: str
    expected: str = "unknown"
    got: str = "unknown"
    hint: str = "Check the YAML contract and required fields."
    source: str = "validation"

    def as_dict(self, attempts: int = 1) -> dict[str, str | int]:
        return {
            "field": self.field,
            "message": self.message,
            "expected": self.expected,
            "got": self.got,
            "hint": self.hint,
            "source": self.source,
            "attempts": attempts,
        }
