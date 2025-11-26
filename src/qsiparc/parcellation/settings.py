"""Parcellation settings and configuration loading."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from qsiparc.parcellation.volume import MetricSpec, DEFAULT_ROI_METRIC_NAMES

try:  # Python 3.11+
    import tomllib  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass(frozen=True)
class ParcellationSettings:
    """Pipeline settings controlling metrics, resampling, and output format."""

    metrics: Sequence[MetricSpec] = DEFAULT_ROI_METRIC_NAMES
    resample_target: str | None = "labels"
    extra: Mapping[str, str] | None = None
    mask: Path | str | None = None


def load_settings(path: Path) -> ParcellationSettings:
    """Load parcellation settings from a TOML file.

    Expected layout:
    [parcellation]
    metrics = ["mean", "median"]
    resample_target = "labels"
    mask = "gm"  # or path
    """

    data = tomllib.loads(path.read_text())
    section = data.get("parcellation", {})
    metrics = tuple(section.get("metrics", DEFAULT_ROI_METRIC_NAMES))
    resample_target = section.get("resample_target", "labels")
    extra = section.get("extra", None)
    mask_value = section.get("mask")
    if isinstance(mask_value, str) and Path(mask_value).exists():
        mask_value = Path(mask_value)
    return ParcellationSettings(metrics=metrics, resample_target=resample_target, extra=extra, mask=mask_value)
