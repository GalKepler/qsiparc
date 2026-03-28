"""Core extraction logic for parcellated diffusion scalar statistics.

This module implements the per-region extraction using direct numpy masking.
We intentionally avoid nilearn's NiftiLabelsMasker because we need access to
the full voxel distribution per region (not just the mean) for computing
robust summary statistics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import nibabel as nib
import numpy as np
import pandas as pd
from scipy import stats as spstats

from qsiparc.atlas import AtlasLUT

logger = logging.getLogger(__name__)

# Default summary statistics to compute for each region.
DEFAULT_STATS = ("mean", "median", "std", "iqr", "skewness", "kurtosis", "n_voxels", "coverage")


@dataclass(frozen=True)
class ExtractionResult:
    """Container for one scalar × one atlas extraction."""

    scalar_name: str
    atlas_name: str
    stats_df: pd.DataFrame  # One row per region, columns = stat names


def compute_region_stats(
    voxels: np.ndarray,
    n_atlas_voxels: int,
    stat_names: tuple[str, ...] = DEFAULT_STATS,
) -> dict[str, float]:
    """Compute summary statistics for an array of voxel values.

    Parameters
    ----------
    voxels : np.ndarray
        1-D array of scalar values within a region (NaNs already excluded).
    n_atlas_voxels : int
        Total number of voxels defined for this region in the atlas dseg,
        used to compute coverage fraction.
    stat_names : tuple[str, ...]
        Which statistics to compute.

    Returns
    -------
    dict[str, float]
        Mapping of stat name → value. NaN for undefined stats (e.g. empty regions).
    """
    result: dict[str, float] = {}

    n_valid = len(voxels)

    for name in stat_names:
        if name == "n_voxels":
            result[name] = float(n_valid)
            continue
        if name == "coverage":
            result[name] = float(n_valid / n_atlas_voxels) if n_atlas_voxels > 0 else np.nan
            continue

        # All remaining stats require at least 1 voxel
        if n_valid == 0:
            result[name] = np.nan
            continue

        if name == "mean":
            result[name] = float(np.mean(voxels))
        elif name == "median":
            result[name] = float(np.median(voxels))
        elif name == "std":
            result[name] = float(np.std(voxels, ddof=1)) if n_valid > 1 else np.nan
        elif name == "iqr":
            q75, q25 = np.percentile(voxels, [75, 25])
            result[name] = float(q75 - q25)
        elif name == "skewness":
            result[name] = float(spstats.skew(voxels, bias=False)) if n_valid > 2 else np.nan
        elif name == "kurtosis":
            result[name] = float(spstats.kurtosis(voxels, bias=False)) if n_valid > 3 else np.nan
        else:
            logger.warning("Unknown stat requested: %s", name)
            result[name] = np.nan

    return result


def extract_scalar_map(
    scalar_path: str | nib.Nifti1Image,
    dseg_path: str | nib.Nifti1Image,
    lut: AtlasLUT,
    scalar_name: str,
    stat_names: tuple[str, ...] = DEFAULT_STATS,
    zero_is_missing: bool = True,
) -> ExtractionResult:
    """Extract per-region statistics from a scalar NIfTI map.

    Parameters
    ----------
    scalar_path : str or Nifti1Image
        Path to the scalar map NIfTI (e.g. FA, MD, ICVF) or a loaded image.
    dseg_path : str or Nifti1Image
        Path to the atlas parcellation dseg NIfTI or a loaded image.
    lut : AtlasLUT
        Region look-up table for labeling output rows.
    scalar_name : str
        Human-readable name for the scalar (used in the output "scalar" column).
    stat_names : tuple[str, ...]
        Which summary statistics to compute.
    zero_is_missing : bool
        If True, treat scalar values of exactly 0.0 as missing data
        (common in masked diffusion maps where background = 0).

    Returns
    -------
    ExtractionResult
        Contains a DataFrame with one row per atlas region.
    """
    # Load images
    scalar_img = nib.load(scalar_path) if isinstance(scalar_path, str) else scalar_path
    dseg_img = nib.load(dseg_path) if isinstance(dseg_path, str) else dseg_path

    scalar_data = np.asarray(scalar_img.dataobj, dtype=np.float64)
    dseg_data = np.asarray(dseg_img.dataobj, dtype=np.int32)

    # Validate shape match
    if scalar_data.shape[:3] != dseg_data.shape[:3]:
        raise ValueError(
            f"Shape mismatch: scalar {scalar_data.shape[:3]} vs dseg {dseg_data.shape[:3]}. "
            "Both must be in the same space (expected: subject T1w space from QSIRecon)."
        )

    # Handle 4D scalar maps (take first volume — e.g. for multi-shell scalars)
    if scalar_data.ndim == 4:
        logger.warning(
            "Scalar map %s is 4D (%s), using first volume only.",
            scalar_name,
            scalar_data.shape,
        )
        scalar_data = scalar_data[..., 0]

    rows = []
    for region in lut.regions:
        mask = dseg_data == region.index
        n_atlas_voxels = int(np.sum(mask))

        if n_atlas_voxels == 0:
            logger.warning(
                "Region %d (%s) has 0 voxels in dseg — atlas/image mismatch?",
                region.index,
                region.name,
            )
            region_stats = compute_region_stats(
                np.array([], dtype=np.float64), 0, stat_names
            )
        else:
            voxels = scalar_data[mask]
            # Exclude NaN and (optionally) zero
            valid_mask = ~np.isnan(voxels)
            if zero_is_missing:
                valid_mask &= voxels != 0.0
            valid_voxels = voxels[valid_mask]

            region_stats = compute_region_stats(valid_voxels, n_atlas_voxels, stat_names)

        rows.append(
            {
                "region_index": region.index,
                "region_name": region.name,
                "hemisphere": region.hemisphere,
                "structure": region.structure,
                "scalar": scalar_name,
                **region_stats,
            }
        )

    df = pd.DataFrame(rows)
    logger.info(
        "Extracted %s for %d regions (atlas=%s)",
        scalar_name,
        len(rows),
        lut.atlas_name,
    )
    return ExtractionResult(scalar_name=scalar_name, atlas_name=lut.atlas_name, stats_df=df)


def merge_extraction_results(results: list[ExtractionResult]) -> pd.DataFrame:
    """Stack multiple ExtractionResults into a single long-format DataFrame.

    Parameters
    ----------
    results : list[ExtractionResult]
        Results from multiple scalar extractions (all for the same atlas).

    Returns
    -------
    pd.DataFrame
        Combined long-format DataFrame with all scalars.
    """
    if not results:
        return pd.DataFrame()
    return pd.concat([r.stats_df for r in results], ignore_index=True)
