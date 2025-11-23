"""IO utilities for discovering QSIRecon outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Mapping

from qsiparc.config import AtlasSelection
from qsiparc.io.data_models import AtlasDefinition, ReconInput, SubjectContext


def load_recon_inputs(root: Path, subjects: Iterable[str]) -> List[ReconInput]:
    """Return stubs for recon inputs discovered under a root directory.

    Actual BIDS/derivative discovery will land here later; for now this
    function only wires the data model and returns empty scalar maps.
    """

    recon_inputs: List[ReconInput] = []
    for subject_id in subjects:
        context = SubjectContext(subject_id=subject_id)
        recon_inputs.append(ReconInput(context=context, scalar_maps={}, mask=None, transforms=()))
    return recon_inputs


def load_atlas_definition(selection: AtlasSelection, atlas_root: Path) -> AtlasDefinition:
    """Load an atlas definition from disk based on a selection.

    This stub records the expected location and yields empty labels. It will
    eventually validate that files exist and read a label LUT.
    """

    labels: Mapping[int, str] = {}
    atlas_path = selection.path or atlas_root / selection.name
    return AtlasDefinition(name=selection.name, path=atlas_path, labels=labels)


def discover_scalar_maps(subject_root: Path) -> Dict[str, Path]:
    """Placeholder for later scalar map discovery."""

    _ = subject_root
    return {}
