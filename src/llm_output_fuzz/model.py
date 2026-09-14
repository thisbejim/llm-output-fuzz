"""Data structures shared by the generator and command-line interface."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Case:
    """One safe-to-store fixture.

    ``payload`` is intentionally data only. The package never executes it,
    evaluates it as Python, or follows paths found in it.
    """

    case_id: str
    mutation: str
    transport: str
    expected_valid: bool
    payload: Any
    json_text: str
    schema_path: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        """Return the stable JSONL representation."""

        return asdict(self)
