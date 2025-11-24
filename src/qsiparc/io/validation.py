"""Validation utilities for inputs and atlases."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from qsiparc.io.data_models import ReconInput


def validate_inputs(recon_inputs: Iterable[ReconInput]) -> list[str]:
    """Return a list of warnings for missing or inconsistent data."""

    warnings: list[str] = []
    for recon in recon_inputs:
        if not recon.scalar_maps:
            warnings.append(f"{recon.context.label}: no scalar maps discovered")
        if recon.mask and not Path(recon.mask).exists():
            warnings.append(f"{recon.context.label}: mask missing at {recon.mask}")
    return warnings

