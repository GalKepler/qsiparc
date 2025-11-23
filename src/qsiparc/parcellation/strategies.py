"""Strategies for parcellation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from qsiparc.io.data_models import ReconInput


@dataclass(frozen=True)
class StrategyParameters:
    """Minimal placeholder for strategy options."""

    apply_smoothing: bool = False
    include_partial_volume: bool = False


class ParcellationStrategy(Protocol):
    """Protocol for parcellation strategies."""

    name: str
    parameters: StrategyParameters

    def apply(self, recon: ReconInput) -> dict[str, float]: ...


@dataclass(frozen=True)
class VolumeParcellationStrategy:
    """Volume-only parcellation strategy placeholder.

    Real implementations will map voxels to atlas labels and aggregate scalar
    maps; this stub returns a deterministic summary keyed by subject label.
    """

    parameters: StrategyParameters = StrategyParameters()
    name: str = "volume"

    def apply(self, recon: ReconInput) -> dict[str, float]:
        """Return a simple summary using discovered scalar maps."""

        map_count = float(len(recon.scalar_maps))
        return {f"{recon.context.label}_map_count": map_count}
