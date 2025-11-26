"""Built-in metrics with descriptions for reporting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

import numpy as np

if TYPE_CHECKING:  # pragma: no cover
    from qsiparc.parcellation.jobs import ParcellationResult


MetricFn = Callable[["ParcellationResult"], float]
RoiMetricFn = Callable[[np.ndarray], float]
RoiMetricSpec = str | RoiMetricFn | tuple[str, RoiMetricFn]


@dataclass(frozen=True)
class BuiltinMetric:
    """A metric with a human-friendly description."""

    name: str
    description: str
    compute: MetricFn


@dataclass(frozen=True)
class RoiStatistic:
    """Statistic applied to ROI voxel values."""

    name: str
    description: str
    compute: RoiMetricFn


def _nanmean(arr: np.ndarray) -> float:
    return float(np.nanmean(arr)) if arr.size else float("nan")


def _nanmedian(arr: np.ndarray) -> float:
    return float(np.nanmedian(arr)) if arr.size else float("nan")


def _nanstd(arr: np.ndarray) -> float:
    return float(np.nanstd(arr)) if arr.size else float("nan")


def _nanmin(arr: np.ndarray) -> float:
    return float(np.nanmin(arr)) if arr.size else float("nan")


def _nanmax(arr: np.ndarray) -> float:
    return float(np.nanmax(arr)) if arr.size else float("nan")


def _count(arr: np.ndarray) -> float:
    return float(arr.size)


def _zfiltered_mean(arr: np.ndarray, threshold: float = 3.0) -> float:
    if arr.size == 0:
        return float("nan")
    mean = np.nanmean(arr)
    std = np.nanstd(arr)
    if std == 0:
        return float(mean)
    z = (arr - mean) / std
    filtered = arr[np.abs(z) < threshold]
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
    median = np.nanmedian(arr)
    mad = np.nanmedian(np.abs(arr - median))
    return float(mad)


ROI_METRICS: Dict[str, RoiStatistic] = {
    "nanmean": RoiStatistic(
        name="nanmean",
        description="Mean ignoring NaNs: mean(x) = sum(x_i) / N_valid",
        compute=_nanmean,
    ),
    "nanmedian": RoiStatistic(
        name="nanmedian",
        description="Median ignoring NaNs: median(x) = 50th percentile of valid values",
        compute=_nanmedian,
    ),
    "nanstd": RoiStatistic(
        name="nanstd",
        description="Std dev ignoring NaNs: std(x) = sqrt(sum((x_i - mean)^2) / N_valid)",
        compute=_nanstd,
    ),
    "nanmin": RoiStatistic(name="nanmin", description="Minimum ignoring NaNs: min(x_i)", compute=_nanmin),
    "nanmax": RoiStatistic(name="nanmax", description="Maximum ignoring NaNs: max(x_i)", compute=_nanmax),
    "count": RoiStatistic(name="count", description="Voxel count (including NaNs): N_total", compute=_count),
    "zfmean": RoiStatistic(
        name="zfmean",
        description="Z-filtered mean: mean(x_i) after removing |(x_i-mean)/std| >= 3",
        compute=_zfiltered_mean,
    ),
    "iqrmean": RoiStatistic(
        name="iqrmean",
        description="Mean within interquartile range: mean(x_i where Q1 <= x_i <= Q3)",
        compute=_iqr_mean,
    ),
    "mad_median": RoiStatistic(
        name="mad_median",
        description="Median absolute deviation: median(|x_i - median(x)|)",
        compute=_mad_median,
    ),
}

# Map legacy/alias names to canonical ROI statistics.
ROI_METRIC_ALIASES: Mapping[str, str] = {
    "mean": "nanmean",
    "median": "nanmedian",
    "std": "nanstd",
    "min": "nanmin",
    "max": "nanmax",
    "count": "count",
    "zfiltered_mean": "zfmean",
    "iqr_mean": "iqrmean",
}

# Default ROI metric names used by parcellation.
DEFAULT_ROI_METRIC_NAMES: tuple[str, ...] = tuple(ROI_METRICS.keys())


def _region_count(result: ParcellationResult) -> float:
    """Count regions that have summaries."""

    return float(len(result.stats))


def _value_count(result: ParcellationResult) -> float:
    """Count summary values across all regions."""

    return float(sum(len(values) for values in result.stats.values()))


def _has_connectivity(result: ParcellationResult) -> float:
    """Flag whether any connectivity values are present."""

    return 1.0 if result.table is not None else 0.0


BUILTIN_METRICS: Dict[str, BuiltinMetric] = {
    "region_count": BuiltinMetric(
        name="region_count",
        description="Number of regions with computed summaries",
        compute=_region_count,
    ),
    "value_count": BuiltinMetric(
        name="value_count",
        description="Number of scalar summary values across all regions",
        compute=_value_count,
    ),
    "connectivity_presence": BuiltinMetric(
        name="connectivity_presence",
        description="1 if connectivity values are present, else 0",
        compute=_has_connectivity,
    ),
}


def list_builtin_metrics() -> List[BuiltinMetric]:
    """Return all built-in metrics."""

    return list(BUILTIN_METRICS.values())


def get_builtin_metric(name: str) -> Optional[BuiltinMetric]:
    """Look up a built-in metric by name."""

    return BUILTIN_METRICS.get(name)


def compute_metrics(names: Iterable[str], result: ParcellationResult) -> Dict[str, float]:
    """Compute selected built-in metrics for a result."""

    output: Dict[str, float] = {}
    for name in names:
        metric = get_builtin_metric(name)
        if metric is None:
            continue
        output[name] = metric.compute(result)
    return output


def list_roi_metrics() -> List[RoiStatistic]:
    """Return all ROI-level statistics."""

    return list(ROI_METRICS.values())


def get_roi_metric(name: str) -> Optional[RoiStatistic]:
    """Look up an ROI-level statistic by name."""

    return ROI_METRICS.get(name)


def resolve_roi_metric_specs(
    metrics: Sequence[RoiMetricSpec] | None,
    *,
    default: Sequence[str] | None = None,
) -> tuple[list[str], list[RoiMetricFn]]:
    """Normalize ROI metric specifications into names and callables.

    Metric specifications can be:
    - a string corresponding to a built-in ROI metric (with aliases handled),
    - a callable, whose ``__name__`` (or ``"custom_metric"``) is used as the column name,
    - a (name, callable) tuple for explicit naming.
    """

    names: list[str] = []
    funcs: list[RoiMetricFn] = []
    specs: Sequence[RoiMetricSpec] = metrics or tuple(default or DEFAULT_ROI_METRIC_NAMES)

    for spec in specs:
        if isinstance(spec, str):
            lookup_name = ROI_METRIC_ALIASES.get(spec, spec)
            metric = get_roi_metric(lookup_name)
            if metric is None:
                raise ValueError(f"Unknown metric: {spec}")
            names.append(spec)
            funcs.append(metric.compute)
            continue

        if callable(spec):
            names.append(getattr(spec, "__name__", "custom_metric"))
            funcs.append(spec)
            continue

        metric_name, metric_func = spec  # type: ignore[misc]
        names.append(metric_name)
        funcs.append(metric_func)

    return names, funcs


def compute_roi_metrics(names: Sequence[str], values: np.ndarray) -> Dict[str, float]:
    """Compute ROI-level statistics on an array of voxel values."""

    metric_names, metric_funcs = resolve_roi_metric_specs(names)
    results: Dict[str, float] = {}
    for name, func in zip(metric_names, metric_funcs):
        results[name] = func(values)
    return results
