"""Job/config/result models for parcellation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence, TYPE_CHECKING

import pandas as pd

from qsiparc.io.data_models import AtlasDefinition, ScalarMapDefinition, SubjectContext
from qsiparc.parcellation.volume import MetricSpec

if TYPE_CHECKING:  # pragma: no cover
    import nibabel as nib


@dataclass(frozen=True)
class ParcellationJob:
    """Pair a scalar map with an atlas in a given space.

    Attributes:
        atlas: Atlas definition (path, metadata).
        scalar: Scalar map definition (path, metadata).
        context: Subject/session context.
        metrics: Metrics to compute per ROI (built-in names or callables).
        resample_target: How to reconcile atlas/scalar grids ("labels"/"data"/None).
        mask: Optional mask (path/keyword/image) applied before aggregation.
    """

    atlas: AtlasDefinition
    scalar: ScalarMapDefinition
    context: SubjectContext
    metrics: Sequence[MetricSpec] = ("mean",)
    resample_target: str | None = "labels"
    mask: Path | str | "nib.Nifti1Image" | None = None


@dataclass(frozen=True)
class ParcellationConfig:
    """Configuration for a parcellation run."""

    output_root: Path | None = None
    extra: Mapping[str, str] | None = None


@dataclass(frozen=True)
class ParcellationResult:
    """Output of a parcellation job."""

    job: ParcellationJob
    stats: dict[str, dict[str, float]]
    table: pd.DataFrame | None = None
    output_path: Path | None = None
