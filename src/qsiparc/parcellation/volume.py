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

_BUILTIN_METRICS: Mapping[str, MetricFunc] = {
    "mean": lambda arr: float(np.mean(arr)) if arr.size else float("nan"),
    "median": lambda arr: float(np.median(arr)) if arr.size else float("nan"),
    "std": lambda arr: float(np.std(arr)) if arr.size else float("nan"),
    "min": lambda arr: float(np.min(arr)) if arr.size else float("nan"),
    "max": lambda arr: float(np.max(arr)) if arr.size else float("nan"),
    "count": lambda arr: float(arr.size),
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
    atlas_path: Path,
    scalar_path: Path,
    metrics: Sequence[MetricSpec] = ("mean",),
    lut: Mapping[int, str] | None = None,
    resample_target: str | None = "labels",
    output_format: str = "dict",
) -> dict[str, dict[str, float]] | pd.DataFrame | tuple[dict[str, dict[str, float]], pd.DataFrame]:
    """Compute distribution metrics per ROI given an atlas and scalar map.

    Args:
        atlas_path: Path to an integer-labeled parcellation image.
        scalar_path: Path to a scalar map aligned with the atlas.
        metrics: Sequence of metrics to compute; can be builtin names
            (mean, median, std, min, max, count) or callables/ (name, func) tuples.
        lut: Optional mapping from label integer to human-readable ROI name.
        resample_target: What to resample if shapes differ: `"labels"`/`"atlas"` (resample scalar to atlas),
            `"data"`/`"scalar"` (resample atlas to scalar), or `None` to raise on mismatch. Mirrors nilearn's
            `resampling_target` semantics.
        output_format: `"dict"`, `"dataframe"`, or `"both"` for both outputs.

    Returns:
        Dictionary keyed by ROI name to metric values, a pandas DataFrame, or both depending on `output_format`.
    """

    atlas_img = nib.load(str(atlas_path))
    scalar_img = nib.load(str(scalar_path))
    atlas_img, scalar_img = _ensure_aligned(atlas_img=atlas_img, scalar_img=scalar_img, resample_target=resample_target)
    atlas = np.asanyarray(atlas_img.dataobj, dtype=int)
    scalars = np.asanyarray(scalar_img.dataobj, dtype=float)

    metric_names, metric_funcs = _resolve_metric_specs(metrics)

    labels = np.unique(atlas)
    labels = labels[labels > 0]  # drop background
    roi_names = [lut[label] if lut and label in lut else str(int(label)) for label in labels]

    values = np.zeros((len(labels), len(metric_funcs)), dtype=float)
    for i, label in enumerate(labels):
        mask = atlas == label
        roi_values = scalars[mask]
        for j, func in enumerate(metric_funcs):
            values[i, j] = func(roi_values)
    stats_dict: dict[str, dict[str, float]] = {
        roi: {metric: float(values[i, j]) for j, metric in enumerate(metric_names)} for i, roi in enumerate(roi_names)
    }
    df = pd.DataFrame(values, index=roi_names, columns=metric_names)

    if output_format == "dict":
        return stats_dict
    if output_format == "dataframe":
        return df
    if output_format == "both":
        return stats_dict, df
    raise ValueError(f"Unknown output_format: {output_format}")


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
