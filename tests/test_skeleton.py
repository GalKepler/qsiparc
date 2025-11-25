from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from qsiparc.atlas.registry import AtlasRegistry
from qsiparc.cli import run_cli
from qsiparc.config import AtlasSelection, ParcellationConfig
from qsiparc.io.loaders import load_recon_inputs
from qsiparc.parcellation.volume import parcellate_volume
from qsiparc.provenance import RunProvenance
from qsiparc.workflows.planner import plan_parcellations
from qsiparc.workflows.runner import WorkflowRunner


def test_workflow_runner_records_provenance(tmp_path: Path) -> None:
    _write_dataset_description(tmp_path)
    _write_scalar_map(tmp_path, subject="01", session=None, desc="fa")
    atlas_path = tmp_path / "atlas.nii.gz"
    nib.Nifti1Image(np.ones((2, 2, 1)), affine=np.eye(4)).to_filename(atlas_path)
    config = ParcellationConfig(
        input_root=tmp_path,
        output_root=tmp_path / "out",
        subjects=["01"],
        atlases=[AtlasSelection(name="test-atlas", path=atlas_path)],
    )
    runner = WorkflowRunner()
    runner.preload_atlases(atlas_root=tmp_path, selections=config.atlases)
    provenance = runner.run(config)
    assert isinstance(provenance, RunProvenance)
    assert provenance.inputs == ["sub-01"]
    assert provenance.outputs


def test_cli_runs_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "outputs"
    input_root.mkdir()
    _write_dataset_description(input_root)
    _write_scalar_map(input_root, subject="02", session=None, desc="fa")
    atlas_path = input_root / "aal.nii.gz"
    nib.Nifti1Image(np.ones((2, 2, 1)), affine=np.eye(4)).to_filename(atlas_path)
    argv = [
        "--input-root",
        str(input_root),
        "--output-root",
        str(output_root),
        "--subject",
        "02",
        "--atlas",
        str(atlas_path),
    ]
    exit_code = run_cli(argv=argv)
    assert exit_code == 0
    summary = output_root / "reports" / "summary.txt"
    assert summary.exists()


def test_atlas_registry_registers_resources(tmp_path: Path) -> None:
    registry = AtlasRegistry()
    runner = WorkflowRunner(atlas_registry=registry)
    atlas_name = "desikan"
    atlas_path = tmp_path / f"{atlas_name}.nii.gz"
    atlas_path.touch()
    runner.preload_atlases(atlas_root=tmp_path, selections=[AtlasSelection(name=atlas_name, path=atlas_path)])
    names = [resource.definition.name for resource in registry.list()]
    assert atlas_name in names


def test_volume_parcellator_runs_with_placeholder_strategy(tmp_path: Path) -> None:
    atlas_path = tmp_path / "atlas.nii.gz"
    scalar_path = tmp_path / "fa.nii.gz"
    atlas_data = np.array([[0, 1], [1, 2]], dtype=np.int16)
    scalar_data = np.array([[0.0, 1.0], [3.0, 5.0]], dtype=np.float32)
    nib.Nifti1Image(atlas_data, affine=np.eye(4)).to_filename(atlas_path)
    nib.Nifti1Image(scalar_data, affine=np.eye(4)).to_filename(scalar_path)

    stats = parcellate_volume(atlas_path=atlas_path, scalar_path=scalar_path, metrics=("mean", "median", "iqr_mean"))
    stats = stats.set_index("index")
    assert stats.loc["1", "mean"] == 2.0
    assert stats.loc["2", "median"] == 5.0
    assert "iqr_mean" in stats.columns


def test_parcellate_volume(tmp_path: Path) -> None:
    atlas_path = tmp_path / "atlas.nii.gz"
    scalar_path = tmp_path / "scalar.nii.gz"
    atlas_data = np.array([[0, 1], [1, 1]], dtype=np.int16)
    scalar_data = np.array([[0.0, 2.0], [4.0, 6.0]], dtype=np.float32)
    nib.Nifti1Image(atlas_data, affine=np.eye(4)).to_filename(atlas_path)
    nib.Nifti1Image(scalar_data, affine=np.eye(4)).to_filename(scalar_path)
    stats = parcellate_volume(atlas_path=atlas_path, scalar_path=scalar_path, metrics=("mean", "max"))
    stats = stats.set_index("index")
    assert stats.loc["1", "mean"] == 4.0
    assert stats.loc["1", "max"] == 6.0


def test_parcellate_volume_resamples_scalar(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("WARNING")
    atlas_path = tmp_path / "atlas.nii.gz"
    scalar_path = tmp_path / "scalar.nii.gz"
    atlas_data = np.ones((2, 2, 1), dtype=np.int16)
    scalar_data = np.ones((4, 4, 1), dtype=np.float32) * 5.0
    nib.Nifti1Image(atlas_data, affine=np.eye(4)).to_filename(atlas_path)
    nib.Nifti1Image(scalar_data, affine=np.eye(4)).to_filename(scalar_path)
    stats = parcellate_volume(
        atlas_path=atlas_path, scalar_path=scalar_path, metrics=("mean",), resample_target="labels"
    )
    stats = stats.set_index("index")
    assert stats.loc["1", "mean"] == 5.0
    assert any("Resampling scalar map to atlas/labels grid" in rec.message for rec in caplog.records)


def test_load_recon_inputs_discovers_atlas_and_scalars(tmp_path: Path) -> None:
    _write_dataset_description(tmp_path)
    _write_scalar_map(tmp_path, subject="01", session="A", desc="fa")
    atlas_file = tmp_path / "sub-01" / "ses-A" / "anat" / "sub-01_ses-A_atlas-aparc_dseg.nii.gz"
    atlas_file.parent.mkdir(parents=True, exist_ok=True)
    nib.Nifti1Image(np.ones((2, 2, 1)), affine=np.eye(4)).to_filename(atlas_file)
    recon_inputs = load_recon_inputs(root=tmp_path, subjects=["01"], sessions=["A"])
    assert len(recon_inputs) == 1
    recon = recon_inputs[0]
    assert recon.context.subject_id == "01"
    assert recon.context.session_id == "A"
    assert recon.scalar_maps
    assert recon.atlases
    assert recon.atlases[0].name == "aparc"


def test_plan_parcellations_matches_space(tmp_path: Path) -> None:
    _write_dataset_description(tmp_path)
    _write_scalar_map(tmp_path, subject="01", session=None, desc="fa", space="MNI152NLin2009cAsym")
    atlas_file = tmp_path / "sub-01" / "anat" / "sub-01_space-MNI152NLin2009cAsym_atlas-aparc_dseg.nii.gz"
    atlas_file.parent.mkdir(parents=True, exist_ok=True)
    nib.Nifti1Image(np.ones((2, 2, 1)), affine=np.eye(4)).to_filename(atlas_file)
    recon_inputs = load_recon_inputs(root=tmp_path, subjects=["01"], sessions=None)
    jobs = plan_parcellations(recon_inputs)
    flat = [job for group in jobs.values() for job in group]
    assert len(flat) == 1
    job = flat[0]
    assert (job.scalar.space or "").lower() == "mni152nlin2009casym"
    assert job.scalar.space.lower() == job.atlas.space.lower()


def _write_dataset_description(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "dataset_description.json").write_text(
        '{"Name": "qsirecon-derivative", "BIDSVersion": "1.8.0", "DatasetType": "derivative"}'
    )


def _write_scalar_map(root: Path, subject: str, session: str | None, desc: str, space: str | None = None) -> Path:
    parts = [f"sub-{subject}"]
    if session:
        parts.append(f"ses-{session}")
    if space:
        parts.append(f"space-{space}")
    name = "_".join([*parts, f"desc-{desc}", "dwimap"]) + ".nii.gz"
    subdir = root / f"sub-{subject}"
    if session:
        subdir = subdir / f"ses-{session}"
    subdir = subdir / "dwi"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / name
    nib.Nifti1Image(np.ones((2, 2, 1)), affine=np.eye(4)).to_filename(path)
    return path
