"""Atlas registry to manage user-provided resources."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from qsiparc.io.data_models import AtlasDefinition


@dataclass(frozen=True)
class AtlasResource:
    """Metadata for an atlas available to the system."""

    definition: AtlasDefinition
    transforms: tuple[Path, ...] = field(default_factory=tuple)


class AtlasRegistry:
    """Simple in-memory registry for atlases."""

    def __init__(self) -> None:
        self._atlases: dict[str, AtlasResource] = {}

    def register(self, resource: AtlasResource) -> None:
        """Add or replace an atlas resource."""

        self._atlases[resource.definition.name] = resource

    def get(self, name: str) -> AtlasResource | None:
        """Return a resource by name."""

        return self._atlases.get(name)

    def list(self) -> Iterable[AtlasResource]:
        """Iterate over registered atlases."""

        return self._atlases.values()
