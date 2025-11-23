"""Region-wise summary metric placeholders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from qsiparc.parcellation.pipeline import ParcellationResult


@dataclass(frozen=True)
class RegionMetric(Protocol):
    """Protocol for a region-wise metric."""

    name: str

    def compute(self, result: ParcellationResult) -> float: ...

