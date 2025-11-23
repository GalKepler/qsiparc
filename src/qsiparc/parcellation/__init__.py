"""Parcellation engines and strategies."""

from qsiparc.parcellation.pipeline import ParcellationPlan, ParcellationResult, Parcellator, VolumeParcellator
from qsiparc.parcellation.strategies import ParcellationStrategy, VolumeParcellationStrategy

__all__ = [
    "ParcellationPlan",
    "ParcellationResult",
    "Parcellator",
    "VolumeParcellator",
    "ParcellationStrategy",
    "VolumeParcellationStrategy",
]
