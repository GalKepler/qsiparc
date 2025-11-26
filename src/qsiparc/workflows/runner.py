"""Workflow runner tying together IO, atlas, parcellation, and reporting."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from qsiparc.atlas.registry import AtlasRegistry, AtlasResource
from qsiparc.config import AtlasSelection, ParcellationConfig
from qsiparc.io.data_models import AtlasDefinition, ReconInput
from qsiparc.io.loaders import load_recon_inputs
from qsiparc.io.validation import validate_inputs
from qsiparc.parcellation import parcellate_volume
from qsiparc.parcellation.settings import ParcellationSettings
from qsiparc.workflows.planner import plan_parcellations
from qsiparc.provenance import RunProvenance


class WorkflowRunner:
    """Orchestrate a parcellation run end-to-end."""

    def __init__(self, atlas_registry: AtlasRegistry | None = None) -> None:
        self.atlas_registry = atlas_registry or AtlasRegistry()

    def preload_atlases(self, atlas_root: Path, selections: Iterable[AtlasSelection]) -> None:
        """Load atlas metadata and register the resources."""

        for selection in selections:
            atlas_path = selection.path or atlas_root / selection.name
            definition = AtlasDefinition(name=selection.name, nifti_path=atlas_path)
            self.atlas_registry.register(resource=self._resource_from_definition(definition))

    def run(self, config: ParcellationConfig) -> RunProvenance:
        """Perform validation and record provenance for a run.

        The heavy lifting (parcellation, metrics, reporting) will plug in here.
        """

        provenance = RunProvenance(parameters={"profile": config.profile})
        recon_inputs = load_recon_inputs(root=config.input_root, subjects=config.subjects)
        self._merge_preloaded_atlases(recon_inputs)
        warnings = validate_inputs(recon_inputs)
        for warning in warnings:
            provenance.add_note(warning)
        for recon in recon_inputs:
            provenance.record_input(recon.context.label)
        plan = plan_parcellations(
            recon_inputs=recon_inputs,
            settings=ParcellationSettings(metrics=tuple(config.metrics.names)),
        )
        for jobs in plan.values():
            for job in jobs:
                stats = parcellate_volume(
                    atlas_path=job.atlas.nifti_path,
                    scalar_path=job.scalar.nifti_path,
                    metrics=job.metrics,
                    lut=job.atlas.lut,
                    resample_target=job.resample_target,
                    mask=job.mask,
                )
                provenance.record_output(
                    f"{job.atlas.name}:{job.context.label}:{job.scalar.name}:{len(stats)}x1"
                )
        provenance.mark_finished()
        return provenance

    def _resource_from_definition(self, definition: AtlasDefinition) -> AtlasResource:
        """Create an atlas resource from a definition."""

        return AtlasResource(definition=definition)

    def _merge_preloaded_atlases(self, recon_inputs: Iterable[ReconInput]) -> None:
        """Add preloaded atlas definitions to each recon input if missing."""

        preloaded = [resource.definition for resource in self.atlas_registry.list()]
        if not preloaded:
            return

        for recon in recon_inputs:
            atlases_by_name = {atlas.name: atlas for atlas in recon.atlases}
            for definition in preloaded:
                atlases_by_name.setdefault(definition.name, definition)
            recon.atlases = tuple(atlases_by_name.values())
