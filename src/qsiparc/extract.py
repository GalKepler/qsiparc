"""Core extraction logic for parcellated diffusion scalar statistics.

Wraps parcellate's VolumetricParcellator to compute per-region statistics from
diffusion scalar maps. The extended statistics tier provides all metrics in
QSIParc's long-format TSV output spec.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd
from parcellate import VolumetricParcellator

from qsiparc.atlas import AtlasLUT

logger = logging.getLogger(__name__)

# Columns returned in ExtractionResult.stats_df — matches CLAUDE.md spec.
OUTPUT_COLUMNS = [
    "region_index",
    "region_name",
    "hemisphere",
    "scalar",
    "mean",
    "median",
    "std",
    "iqr",
    "skewness",
    "kurtosis",
    "n_voxels",
    "coverage",
]


@dataclass(frozen=True)
class ExtractionResult:
    """Container for one scalar × one atlas extraction."""

    scalar_name: str
    atlas_name: str
    stats_df: pd.DataFrame  # One row per region, columns = OUTPUT_COLUMNS (see above)


def _lut_to_dataframe(lut: AtlasLUT) -> pd.DataFrame:
    """Convert AtlasLUT to the format expected by VolumetricParcellator.

    Returns a DataFrame with 'index', 'label', plus hemisphere
    as passthrough columns.
    """
    return pd.DataFrame(
        [
            {
                "index": r.index,
                "label": r.name,
                "hemisphere": r.hemisphere,
            }
            for r in lut.regions
        ]
    )


def extract_scalar_map(
    scalar_path: str | Path | nib.Nifti1Image,
    dseg_path: str | Path | nib.Nifti1Image,
    lut: AtlasLUT,
    scalar_name: str,
    zero_is_missing: bool = True,
) -> ExtractionResult:
    """Extract per-region statistics from a scalar NIfTI map.

    Parameters
    ----------
    scalar_path : str, Path, or Nifti1Image
        Scalar map NIfTI (e.g. FA, MD, ICVF).
    dseg_path : str, Path, or Nifti1Image
        Atlas parcellation dseg NIfTI (subject diffusion space).
    lut : AtlasLUT
        Region look-up table for labeling output rows.
    scalar_name : str
        Human-readable name for the scalar (written to the "scalar" column).
    zero_is_missing : bool
        If True, treat scalar values of exactly 0.0 as NaN before extraction.
        Common in masked diffusion maps where background = 0.

    Returns
    -------
    ExtractionResult
        DataFrame with one row per atlas region and columns per OUTPUT_COLUMNS.
    """
    scalar_img = (
        nib.load(scalar_path) if isinstance(scalar_path, str | Path) else scalar_path
    )
    dseg_img = (
        nib.load(dseg_path) if isinstance(dseg_path, str | Path) else dseg_path
    )

    scalar_data = np.asarray(scalar_img.dataobj, dtype=np.float64)
    dseg_data = np.round(np.asarray(dseg_img.dataobj, dtype=np.int32))

    if scalar_data.shape[:3] != dseg_data.shape[:3]:
        raise ValueError(
            f"Shape mismatch: scalar {scalar_data.shape[:3]}"
            f" vs dseg {dseg_data.shape[:3]}. "
            "Both must be in the same space "
            "(expected: subject T1w space from QSIRecon)."
        )

    if scalar_data.ndim == 4:
        logger.warning(
            "Scalar map %s is 4D (%s), using first volume only.",
            scalar_name,
            scalar_data.shape,
        )
        scalar_data = scalar_data[..., 0]
        scalar_img = nib.Nifti1Image(
            scalar_data, scalar_img.affine, scalar_img.header
        )

    if zero_is_missing:
        scalar_data = scalar_data.copy()
        scalar_data[scalar_data == 0.0] = np.nan
        scalar_img = nib.Nifti1Image(
            scalar_data, scalar_img.affine, scalar_img.header
        )

    # Compute n_voxels and coverage from the already-loaded arrays.
    # parcellate's voxel_count is the total atlas count, not the valid-signal count.
    # n_voxels = valid (non-NaN) voxels; coverage = n_voxels / n_atlas_voxels.
    region_voxel_stats: dict[int, tuple[float, float]] = {}
    for region in lut.regions:
        n_atlas = int(np.sum(dseg_data == region.index))
        if n_atlas == 0:
            region_voxel_stats[region.index] = (0.0, np.nan)
        else:
            n_valid = float(np.sum(~np.isnan(scalar_data[dseg_data == region.index])))
            region_voxel_stats[region.index] = (n_valid, n_valid / n_atlas)

    lut_df = _lut_to_dataframe(lut)

    # atlas and scalar are already co-registered by QSIRecon — skip resampling
    parcellator = VolumetricParcellator(
        atlas_img=dseg_img,
        lut=lut_df,
        stat_tier="extended",
        resampling_target=None,
    )
    parcellator.fit(scalar_img)
    stats_df = parcellator.transform(scalar_img)
    stats_df["scalar"] = scalar_name

    logger.info(
        "Extracted %s for %d regions (atlas=%s)",
        scalar_name,
        len(stats_df),
        lut.atlas_name,
    )
    return ExtractionResult(
        scalar_name=scalar_name, atlas_name=lut.atlas_name, stats_df=stats_df
    )


def merge_extraction_results(results: list[ExtractionResult]) -> pd.DataFrame:
    """Stack multiple ExtractionResults into a single long-format DataFrame."""
    if not results:
        return pd.DataFrame()
    return pd.concat([r.stats_df for r in results], ignore_index=True)
