from pathlib import Path

from qsiparc.io.data_models import AtlasDefinition, ScalarMapDefinition, SubjectContext
import numpy as np

from qsiparc.metrics.metrics import (
    BUILTIN_METRICS,
    ROI_METRICS,
    compute_metrics,
    compute_roi_metrics,
    get_builtin_metric,
    get_roi_metric,
    list_builtin_metrics,
    list_roi_metrics,
)
from qsiparc.parcellation.jobs import ParcellationJob, ParcellationResult


def _dummy_result(tmp_path: Path) -> ParcellationResult:
    atlas = AtlasDefinition(name="atlas", nifti_path=tmp_path / "atlas.nii.gz")
    scalar = ScalarMapDefinition(name="fa", nifti_path=tmp_path / "fa.nii.gz")
    job = ParcellationJob(atlas=atlas, scalar=scalar, context=SubjectContext(subject_id="01"))
    stats = {"1": {"FA": 1.0, "MD": 2.0}, "2": {"FA": 3.0}}
    return ParcellationResult(job=job, stats=stats)


def test_builtin_metrics_are_described(tmp_path: Path) -> None:
    metrics = list_builtin_metrics()
    assert metrics, "expected at least one built-in metric"
    for metric in metrics:
        assert metric.description


def test_compute_metrics_returns_values(tmp_path: Path) -> None:
    result = _dummy_result(tmp_path)
    values = compute_metrics(names=list(BUILTIN_METRICS.keys()), result=result)
    assert set(values) == set(BUILTIN_METRICS.keys())
    assert values["region_count"] == 2.0
    assert values["value_count"] == 3.0
    assert values["connectivity_presence"] == 0.0


def test_get_builtin_metric_handles_missing() -> None:
    assert get_builtin_metric("nonexistent") is None


def test_roi_metrics_cover_expected_names() -> None:
    expected = {"nanmean", "nanmedian", "nanstd", "nanmin", "nanmax", "count", "zfmean", "iqrmean", "mad_median"}
    names = {metric.name for metric in list_roi_metrics()}
    assert expected.issubset(names)
    descriptions = [metric.description for metric in list_roi_metrics()]
    assert all(descriptions)


def test_compute_roi_metrics_handles_nans() -> None:
    arr = np.array([1.0, 2.0, np.nan, 100.0])
    values = compute_roi_metrics(names=["nanmean", "nanmedian", "nanstd", "zfmean", "iqrmean", "mad_median"], values=arr)
    assert not np.isnan(values["nanmean"])
    assert values["nanmedian"] == 2.0
    assert "zfmean" in values
    assert "iqrmean" in values
    assert values["mad_median"] >= 0


def test_get_roi_metric_handles_missing() -> None:
    assert get_roi_metric("missing") is None
