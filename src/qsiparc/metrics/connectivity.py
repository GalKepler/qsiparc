"""Connectivity metric placeholders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ConnectivityMetric(Protocol):
    """Protocol for a connectivity metric."""

    name: str

    def compute(self, *args, **kwargs) -> float: ...
