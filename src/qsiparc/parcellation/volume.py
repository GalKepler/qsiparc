"""Volume parcellation utilities.

The core entrypoint `parcellate_volume` returns a pandas DataFrame with per-ROI
statistics computed over a scalar map, aligned to an atlas. Masking, LUT
labeling, resampling, and custom metrics are supported.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Union

import nibabel as nib
import numpy as np
import pandas as pd
from nibabel.processing import resample_from_to

from qsiparc.metrics import DEFAULT_ROI_METRIC_NAMES, resolve_roi_metric_specs
from qsiparc.metrics.metrics import RoiMetricSpec

MetricSpec = RoiMetricSpec
ImageLike = Union[Path, nib.Nifti1Image]

logger = logging.getLogger(__name__)


def parcellate_volume(
    atlas_path: ImageLike,
    scalar_path: ImageLike,
    metrics: Sequence[MetricSpec] | None = None,
    lut: Mapping[int, str] | None = None,
    resample_target: str | None = "labels",
    output_format: str | None = None,
    mask: Path | str | nib.Nifti1Image | None = None,
) -> pd.DataFrame:
    """Compute distribution metrics per ROI given an atlas and scalar map.

    Args:
        atlas_path: Path to an integer-labeled parcellation image.
        scalar_path: Path to a scalar map aligned with the atlas.
        metrics: Sequence of metrics to compute; can be built-in ROI metric names
            (see ``qsiparc.metrics.ROI_METRICS``), legacy aliases (mean, median, std,
            min, max, count, zfiltered_mean, iqr_mean), callables, or (name, func)
            tuples. Defaults to all built-in ROI metrics.
        lut: Optional mapping from label integer to human-readable ROI name. When provided, the function will
            include ROI/label columns in the DataFrame and return a DataFrame when `output_format="dict"`.
        resample_target: What to resample if shapes differ: `"labels"`/`"atlas"` (resample scalar to atlas),
            `"data"`/`"scalar"` (resample atlas to scalar), or `None` to raise on mismatch. Mirrors nilearn's
            `resampling_target` semantics.
        output_format: Ignored; always returns a DataFrame with `label` and `index` columns.
        mask: Optional mask image (atlas space) to zero out labels before metric computation. If a string of
            "gm", "wm", or "csf" is provided, nilearn's corresponding MNI mask loader will be used.

    Returns:
        Pandas DataFrame indexed by ROI with metric columns (plus label/name metadata).
    """

    atlas_img = _ensure_img(atlas_path)
    scalar_img = _ensure_img(scalar_path)
    atlas_img, scalar_img = _ensure_aligned(atlas_img=atlas_img, scalar_img=scalar_img, resample_target=resample_target)
    atlas = np.asanyarray(atlas_img.dataobj, dtype=int)
    scalars = np.asanyarray(scalar_img.dataobj, dtype=float)
    if mask is not None:
        mask_img = _load_mask(mask)
        if mask_img.shape != atlas_img.shape:
            mask_img = resample_from_to(mask_img, atlas_img, order=0)
        mask_data = np.asanyarray(mask_img.dataobj, dtype=bool)
        atlas = np.where(mask_data, atlas, 0)

    metric_names, metric_funcs = resolve_roi_metric_specs(metrics, default=DEFAULT_ROI_METRIC_NAMES)

    if lut is None:
        labels = np.unique(atlas)
        labels = labels[labels > 0]  # drop background
        roi_names = [str(int(label)) for label in labels]
        lut_names: list[str | int] = roi_names
    else:
        # lut may be a mapping or path; if mapping, keep the label order from the atlas.
        if isinstance(lut, Path):
            parcels = pd.read_csv(lut, sep="\t")
            label_to_name = dict(zip(parcels["index"], parcels["label"]))
        else:
            label_to_name = dict(lut)
        labels = np.unique(atlas)
        labels = labels[labels > 0]
        roi_names = [str(int(label)) for label in labels]
        lut_names = [label_to_name.get(int(label), str(int(label))) for label in labels]

    values = np.zeros((len(labels), len(metric_funcs)), dtype=float)
    for i, label in enumerate(labels):
        mask = atlas == label
        roi_values = scalars[mask]
        for j, func in enumerate(metric_funcs):
            values[i, j] = func(roi_values)
    df = pd.DataFrame(values, index=roi_names, columns=metric_names)
    df.insert(0, "index", roi_names)
    df.insert(1, "label", list(labels.astype(int)))
    if lut is not None:
        df.insert(2, "name", lut_names)
    return df


def _ensure_aligned(
    atlas_img: nib.spatialimages.SpatialImage, scalar_img: nib.spatialimages.SpatialImage, resample_target: str | None
):
    """Ensure atlas and scalar images share shape; resample if configured.

    resample_target follows nilearn semantics:
    - "labels"/"atlas": resample scalar data to atlas grid (linear interp).
    - "data"/"scalar": resample atlas labels to scalar grid (nearest interp).
    """

    if atlas_img.shape == scalar_img.shape:
        return atlas_img, scalar_img

    message = f"Atlas shape {atlas_img.shape} does not match scalar shape {scalar_img.shape}"
    if resample_target is None:
        raise ValueError(message)

    if resample_target in {"atlas", "labels"}:
        logger.warning("%s. Resampling scalar map to atlas/labels grid.", message)
        scalar_img = resample_from_to(scalar_img, atlas_img, order=1)
    elif resample_target in {"scalar", "data"}:
        logger.warning("%s. Resampling atlas/labels to scalar/data grid.", message)
        atlas_img = resample_from_to(atlas_img, scalar_img, order=0)
    else:
        raise ValueError(f"Unknown resample_target: {resample_target}")
    return atlas_img, scalar_img


def _ensure_img(img: ImageLike) -> nib.Nifti1Image:
    """Return a loaded NIfTI image from a path or existing image."""

    return nib.load(str(img)) if isinstance(img, Path) else img


def _load_mask(mask: Path | str | nib.Nifti1Image) -> nib.Nifti1Image:
    """Load a mask from path, image, or nilearn keyword."""

    if isinstance(mask, nib.spatialimages.SpatialImage):
        return mask
    if isinstance(mask, Path):
        return nib.load(str(mask))
    if isinstance(mask, str):
        from nilearn import datasets

        key = mask.lower()
        if key == "gm":
            return datasets.load_mni152_gm_mask()
        if key == "wm":
            return datasets.load_mni152_wm_mask()
        if key == "csf":
            return datasets.load_mni152_csf_mask()
        # fallback to loading as a path-like string
        return nib.load(mask)
    raise ValueError(f"Unsupported mask type: {type(mask)}")
