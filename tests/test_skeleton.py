from pathlib import Path

import pytest

from qsiparc.atlas.registry import AtlasRegistry, AtlasResource
from qsiparc.cli import run_cli
from qsiparc.config import AtlasSelection, ParcellationConfig
from qsiparc.io.data_models import AtlasDefinition, ReconInput, SubjectContext
from qsiparc.parcellation.pipeline import ParcellationPlan, VolumeParcellator
from qsiparc.parcellation.strategies import VolumeParcellationStrategy
from qsiparc.provenance import RunProvenance
from qsiparc.workflows.runner import WorkflowRunner


def test_workflow_runner_records_provenance(tmp_path: Path) -> None:
    atlas_path = tmp_path / "atlas.nii.gz"
    atlas_path.touch()
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
    assert any("no scalar maps" in note for note in provenance.notes)


def test_cli_runs_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "outputs"
    input_root.mkdir()
    atlas_path = input_root / "aal.nii.gz"
    atlas_path.touch()
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
    atlas_path.touch()
    selection = AtlasSelection(name="atlas", path=atlas_path)
    resource = AtlasResource(definition=AtlasDefinition(name=selection.name, path=selection.path, labels={}))
    recon_input = ReconInput(context=SubjectContext(subject_id="01"), scalar_maps={}, mask=None, transforms=())
    strategy = VolumeParcellationStrategy()
    parcellator = VolumeParcellator(strategy=strategy)
    plan = ParcellationPlan(atlas=resource, inputs=[recon_input], strategy=strategy)
    result = parcellator.run(plan)
    assert "sub-01" in result.region_summaries
