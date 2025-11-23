"""Configuration objects and defaults for parcellation runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


@dataclass(frozen=True)
class AtlasSelection:
    """Atlas requested for a run, provided by path or discovered in recon outputs."""

    name: str
    path: Optional[Path] = None
    resolution: Optional[str] = None


@dataclass(frozen=True)
class MetricSelection:
    """Metric identifiers to compute during parcellation."""

    names: Sequence[str] = field(default_factory=tuple)
    connectivity: bool = False


@dataclass(frozen=True)
class ParcellationConfig:
    """Top-level knobs to drive workflows."""

    input_root: Path
    output_root: Path
    subjects: Iterable[str]
    atlases: List[AtlasSelection] = field(default_factory=list)
    metrics: MetricSelection = field(default_factory=MetricSelection)
    profile: str = "volume"  # e.g., volume or surface modes
    extra: Dict[str, str] = field(default_factory=dict)

    def ensure_output_root(self) -> Path:
        """Return the output root and create it if needed."""

        self.output_root.mkdir(parents=True, exist_ok=True)
        return self.output_root
