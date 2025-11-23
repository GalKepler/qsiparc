"""Structured representations of inputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


@dataclass(frozen=True)
class SubjectContext:
    """Minimal BIDS-like identifier for a subject/session."""

    subject_id: str
    session_id: str | None = None

    @property
    def label(self) -> str:
        """Return a compact label suitable for filenames."""

        return f"sub-{self.subject_id}" + (f"_ses-{self.session_id}" if self.session_id else "")


@dataclass(frozen=True)
class AtlasDefinition:
    """Description of an atlas available to the pipeline."""

    name: str
    path: Path
    labels: Mapping[int, str]
    resolution: str | None = None


@dataclass(frozen=True)
class ReconInput:
    """Paths to QSIRecon outputs required for parcellation."""

    context: SubjectContext
    scalar_maps: Mapping[str, Path]
    mask: Path | None = None
    transforms: Sequence[Path] = ()

