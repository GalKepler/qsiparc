"""Parcellation planning: generate atlas-scalar combinations by space."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import List

from qsiparc.io.data_models import AtlasDefinition, ReconInput, ScalarMapDefinition


@dataclass(frozen=True)
class ParcellationJob:
    """Pair a scalar map with an atlas in a given space."""

    atlas: AtlasDefinition
    scalar: ScalarMapDefinition
    space: str | None
    context_label: str


def plan_parcellations(
    recon_inputs: Sequence[ReconInput], spaces: Iterable[str] | None = ("MNI152NLin2009cAsym", "ACPC")
) -> List[ParcellationJob]:
    """Create atlas-scalar combinations constrained by space."""

    allowed_spaces = {s.lower() for s in spaces} if spaces else None
    jobs: List[ParcellationJob] = []
    for recon in recon_inputs:
        atlases = list(recon.atlases) + list(recon.native_atlases or [])
        for atlas in atlases:
            for scalar in recon.scalar_maps:
                if not _spaces_compatible(atlas.space, scalar.space, allowed_spaces):
                    continue
                space = scalar.space or atlas.space
                jobs.append(ParcellationJob(atlas=atlas, scalar=scalar, space=space, context_label=recon.context.label))
    return jobs


def _spaces_compatible(atlas_space: str | None, scalar_space: str | None, allowed: set[str] | None) -> bool:
    """Return True if atlas and scalar share a permitted space."""

    a = atlas_space.lower() if atlas_space else None
    s = scalar_space.lower() if scalar_space else None
    if allowed is not None:
        if a and a not in allowed and s and s not in allowed:
            return False
    if a and s:
        return a == s
    # If one is missing, allow pairing but still respect allowed set.
    if allowed is not None and (a or s):
        return (a in allowed) or (s in allowed)
    return True
