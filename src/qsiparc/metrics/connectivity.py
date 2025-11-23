"""Connectivity metric placeholders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from qsiparc.parcellation.pipeline import ParcellationResult


@dataclass(frozen=True)
class ConnectivityMetric(Protocol):
    """Protocol for a connectivity metric."""

    name: str

    def compute(self, result: ParcellationResult) -> float: ...

