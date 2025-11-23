"""Core parcellation runner interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Protocol

from qsiparc.atlas.registry import AtlasResource
from qsiparc.io.data_models import ReconInput
from qsiparc.parcellation.strategies import ParcellationStrategy, VolumeParcellationStrategy


@dataclass(frozen=True)
class ParcellationPlan:
    """A declared run: which atlas, inputs, and strategy."""

    atlas: AtlasResource
    inputs: Iterable[ReconInput]
    strategy: ParcellationStrategy


@dataclass
class ParcellationResult:
    """Placeholder parcellation outputs."""

    region_summaries: Dict[str, Dict[str, float]]
    connectivity: Dict[str, float]


class Parcellator(Protocol):
    """Protocol for objects capable of performing parcellation."""

    def run(self, plan: ParcellationPlan) -> ParcellationResult: ...


class VolumeParcellator:
    """Basic parcellator that applies a volume strategy per subject."""

    def __init__(self, strategy: ParcellationStrategy | None = None) -> None:
        self.strategy = strategy or VolumeParcellationStrategy()

    def run(self, plan: ParcellationPlan) -> ParcellationResult:
        """Apply the strategy across inputs and collect summaries."""

        region_summaries: Dict[str, Dict[str, float]] = {}
        for recon in plan.inputs:
            region_summaries[recon.context.label] = plan.strategy.apply(recon)
        return ParcellationResult(region_summaries=region_summaries, connectivity={})
