"""Base definitions for provider usage normalization (INV-06)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NormalizedUsage:
    """Canonical usage accounting where read + write + uncached == total_input (INV-06)."""

    read: int
    write: int
    uncached: int
    output: int
    total_input: int
    raw: dict[str, Any]

    def __post_init__(self) -> None:
        if self.read + self.write + self.uncached != self.total_input:
            raise ValueError(
                f"Usage does not reconcile: read ({self.read}) + write ({self.write}) + "
                f"uncached ({self.uncached}) != total_input ({self.total_input})"
            )
