"""Workflow runner tying together IO, atlas, parcellation, and reporting."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from qsiparc.atlas.registry import AtlasRegistry, AtlasResource
from qsiparc.config import AtlasSelection, ParcellationConfig
from qsiparc.io.data_models import AtlasDefinition
from qsiparc.io.loaders import load_atlas_definition, load_recon_inputs
from qsiparc.io.validation import validate_inputs
from qsiparc.parcellation import parcellate_volume
from qsiparc.provenance import RunProvenance


class WorkflowRunner:
    """Orchestrate a parcellation run end-to-end."""

    def __init__(self, atlas_registry: AtlasRegistry | None = None) -> None:
        self.atlas_registry = atlas_registry or AtlasRegistry()

    def preload_atlases(self, atlas_root: Path, selections: Iterable[AtlasSelection]) -> None:
        """Load atlas metadata and register the resources."""

        for selection in selections:
            definition = load_atlas_definition(selection=selection, atlas_root=atlas_root)
            self.atlas_registry.register(resource=self._resource_from_definition(definition))

    def run(self, config: ParcellationConfig) -> RunProvenance:
        """Perform validation and record provenance for a run.

        The heavy lifting (parcellation, metrics, reporting) will plug in here.
        """

        provenance = RunProvenance(parameters={"profile": config.profile})
        recon_inputs = load_recon_inputs(root=config.input_root, subjects=config.subjects)
        warnings = validate_inputs(recon_inputs)
        for warning in warnings:
            provenance.add_note(warning)
        for recon in recon_inputs:
            provenance.record_input(recon.context.label)
        for resource in self.atlas_registry.list():
            for recon in recon_inputs:
                for scalar_name, scalar_path in recon.scalar_maps.items():
                    stats = parcellate_volume(
                        atlas_path=resource.definition.path,
                        scalar_path=scalar_path,
                        metrics=("mean",),
                        lut=resource.definition.labels,
                    )
                    provenance.record_output(
                        f"{resource.definition.name}:{recon.context.label}:{scalar_name}:"
                        f"{len(stats)}x1"
                    )
        provenance.mark_finished()
        return provenance

    def _resource_from_definition(self, definition: AtlasDefinition) -> AtlasResource:
        """Create an atlas resource from a definition."""

        return AtlasResource(definition=definition)
