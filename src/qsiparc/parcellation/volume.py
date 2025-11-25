"""Volume parcellation utilities."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Callable

import nibabel as nib
import numpy as np
import pandas as pd
from nibabel.processing import resample_from_to

MetricFunc = Callable[[np.ndarray], float]
MetricSpec = str | MetricFunc | tuple[str, MetricFunc]

logger = logging.getLogger(__name__)


def _zfiltered_mean(arr: np.ndarray) -> float:
    if arr.size == 0:
        return float("nan")
    mean = np.nanmean(arr)
    std = np.nanstd(arr)
    if std == 0:
        return float(mean)
    z = (arr - mean) / std
    filtered = arr[np.abs(z) < 3]
    return float(np.nanmean(filtered)) if filtered.size else float("nan")


def _iqr_mean(arr: np.ndarray) -> float:
    if arr.size == 0:
        return float("nan")
    q1, q3 = np.percentile(arr, [25, 75])
    mask = (arr >= q1) & (arr <= q3)
    subset = arr[mask]
    return float(np.mean(subset)) if subset.size else float("nan")


def _mad_median(arr: np.ndarray) -> float:
    if arr.size == 0:
        return float("nan")
    median = np.median(arr)
    mad = np.median(np.abs(arr - median))
    return float(mad)


_BUILTIN_METRICS: Mapping[str, MetricFunc] = {
    "mean": lambda arr: float(np.nanmean(arr)) if arr.size else float("nan"),
    "median": lambda arr: float(np.nanmedian(arr)) if arr.size else float("nan"),
    "std": lambda arr: float(np.nanstd(arr)) if arr.size else float("nan"),
    "min": lambda arr: float(np.nanmin(arr)) if arr.size else float("nan"),
    "max": lambda arr: float(np.nanmax(arr)) if arr.size else float("nan"),
    "count": lambda arr: float(arr.size),
    "zfiltered_mean": _zfiltered_mean,
    "iqr_mean": _iqr_mean,
    "mad_median": _mad_median,
}


def _resolve_metric_specs(metrics: Sequence[MetricSpec]) -> tuple[list[str], list[MetricFunc]]:
    names: list[str] = []
    funcs: list[MetricFunc] = []
    if not metrics:
        metrics = ("mean",)
    for spec in metrics:
        if isinstance(spec, str):
            if spec not in _BUILTIN_METRICS:
                raise ValueError(f"Unknown metric: {spec}")
            names.append(spec)
            funcs.append(_BUILTIN_METRICS[spec])
        elif callable(spec):
            names.append(getattr(spec, "__name__", "custom_metric"))
            funcs.append(spec)  # type: ignore[arg-type]
        else:
            metric_name, metric_func = spec  # type: ignore[misc]
            names.append(metric_name)
            funcs.append(metric_func)
    return names, funcs


def parcellate_volume(
    atlas_path: Path | nib.Nifti1Image,
    scalar_path: Path | nib.Nifti1Image,
    metrics: Sequence[MetricSpec] = tuple(_BUILTIN_METRICS.keys()),
    lut: Mapping[int, str] | None = None,
    resample_target: str | None = "labels",
    output_format: str = "dataframe",
    mask: Path | str | nib.Nifti1Image | None = None,
) -> pd.DataFrame:
    """Compute distribution metrics per ROI given an atlas and scalar map.

    Args:
        atlas_path: Path to an integer-labeled parcellation image.
        scalar_path: Path to a scalar map aligned with the atlas.
        metrics: Sequence of metrics to compute; can be builtin names
            (mean, median, std, min, max, count) or callables/ (name, func) tuples.
        lut: Optional mapping from label integer to human-readable ROI name. When provided, the function will
            include ROI/label columns in the DataFrame and return a DataFrame when `output_format="dict"`.
        resample_target: What to resample if shapes differ: `"labels"`/`"atlas"` (resample scalar to atlas),
            `"data"`/`"scalar"` (resample atlas to scalar), or `None` to raise on mismatch. Mirrors nilearn's
            `resampling_target` semantics.
        output_format: Ignored; always returns a DataFrame with `label` and `index` columns.
        mask: Optional mask image (atlas space) to zero out labels before metric computation. If a string of
            "gm", "wm", or "csf" is provided, nilearn's corresponding MNI mask loader will be used.

    Returns:
        Dictionary keyed by ROI name to metric values, a pandas DataFrame, or both depending on `output_format`.
    """

    atlas_img = nib.load(str(atlas_path)) if isinstance(atlas_path, Path) else atlas_path
    scalar_img = nib.load(str(scalar_path)) if isinstance(scalar_path, Path) else scalar_path
    atlas_img, scalar_img = _ensure_aligned(atlas_img=atlas_img, scalar_img=scalar_img, resample_target=resample_target)
    atlas = np.asanyarray(atlas_img.dataobj, dtype=int)
    scalars = np.asanyarray(scalar_img.dataobj, dtype=float)
    if mask is not None:
        mask_img = _load_mask(mask)
        if mask_img.shape != atlas_img.shape:
            mask_img = resample_from_to(mask_img, atlas_img, order=0)
        mask_data = np.asanyarray(mask_img.dataobj, dtype=bool)
        atlas = np.where(mask_data, atlas, 0)

    metric_names, metric_funcs = _resolve_metric_specs(metrics)

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
