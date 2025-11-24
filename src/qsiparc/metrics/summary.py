"""Region-wise summary metric placeholders."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RegionMetric(Protocol):
    """Protocol for a region-wise metric operating on parcellation statistics."""

    name: str

    def compute(self, stats: Mapping[str, Mapping[str, float]]) -> float: ...
