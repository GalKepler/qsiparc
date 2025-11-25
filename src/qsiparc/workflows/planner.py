"""Parcellation planning: generate atlas-scalar combinations by space."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Dict, List

from qsiparc.io.data_models import AtlasDefinition, ReconInput
from qsiparc.parcellation.jobs import ParcellationJob
from qsiparc.parcellation.settings import ParcellationSettings


def plan_parcellations(
    recon_inputs: Sequence[ReconInput],
    spaces: Iterable[str] | None = ("MNI152NLin2009cAsym", "ACPC"),
    settings: ParcellationSettings | None = None,
) -> Dict[str, List[ParcellationJob]]:
    """Create atlas -> list of jobs constrained by space."""

    allowed_spaces = {s.lower() for s in spaces} if spaces else None
    settings = settings or ParcellationSettings()
    plan: Dict[str, List[ParcellationJob]] = {}
    for recon in recon_inputs:
        atlases = list(recon.atlases) + list(recon.native_atlases or [])
        for atlas in atlases:
            for scalar in recon.scalar_maps:
                if not _spaces_compatible(atlas.space, scalar.space, allowed_spaces):
                    continue
                key = f"{atlas.name}:{recon.context.label}"
                plan.setdefault(key, []).append(
                    ParcellationJob(
                        atlas=atlas,
                        scalar=scalar,
                        context=recon.context,
                        metrics=settings.metrics,
                        resample_target=settings.resample_target,
                        mask=settings.mask,
                    )
                )
    return plan


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
