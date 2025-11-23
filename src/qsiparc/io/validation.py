"""Validation utilities for inputs and atlases."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from qsiparc.io.data_models import ReconInput


def validate_inputs(recon_inputs: Iterable[ReconInput]) -> List[str]:
    """Return a list of warnings for missing or inconsistent data."""

    warnings: List[str] = []
    for recon in recon_inputs:
        if not recon.scalar_maps:
            warnings.append(f"{recon.context.label}: no scalar maps discovered")
        if recon.mask and not Path(recon.mask).exists():
            warnings.append(f"{recon.context.label}: mask missing at {recon.mask}")
    return warnings

