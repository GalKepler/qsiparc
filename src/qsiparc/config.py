"""Configuration objects and defaults for parcellation runs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass(frozen=True)
class AtlasSelection:
    """Atlas requested for a run, provided by path or discovered in recon outputs."""

    name: str
    path: Path | None = None
    resolution: str | None = None


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
    atlases: list[AtlasSelection] = field(default_factory=list)
    metrics: MetricSelection = field(default_factory=MetricSelection)
    profile: str = "volume"  # e.g., volume or surface modes
    extra: dict[str, str] = field(default_factory=dict)

    def ensure_output_root(self) -> Path:
        """Return the output root and create it if needed."""

        self.output_root.mkdir(parents=True, exist_ok=True)
        return self.output_root


def _require(mapping: Mapping[str, Any], key: str) -> Any:
    """Return a required key from a mapping or raise a ValueError."""

    try:
        return mapping[key]
    except KeyError as exc:  # pragma: no cover - simple passthrough
        raise ValueError(f"Missing required configuration field: '{key}'") from exc


def _parse_atlas_entry(entry: str | Mapping[str, Any]) -> AtlasSelection:
    """Normalise atlas entries from TOML into AtlasSelection instances."""

    if isinstance(entry, str):
        return AtlasSelection(name=entry)
    if isinstance(entry, Mapping):
        name = entry.get("name")
        if not name:
            raise ValueError("Atlas entries must include a 'name'.")
        path = Path(entry["path"]) if "path" in entry else None
        resolution = entry.get("resolution")
        return AtlasSelection(name=name, path=path, resolution=resolution)
    raise ValueError("Atlas entries must be strings or tables.")


def load_parcellation_config(path: Path) -> ParcellationConfig:
    """Load a :class:`ParcellationConfig` from a TOML file.

    The expected schema is a ``[parcellation]`` table with required
    ``input_root``, ``output_root`` and ``subjects`` fields. Atlases can be
    provided either as strings (atlas names) or as tables with ``name`` and an
    optional ``path`` or ``resolution``.
    """

    with path.open("rb") as config_file:
        contents = tomllib.load(config_file)

    parcellation = contents.get("parcellation", contents)
    input_root = Path(_require(parcellation, "input_root"))
    output_root = Path(_require(parcellation, "output_root"))
    subjects_value = _require(parcellation, "subjects")
    if isinstance(subjects_value, str):
        subjects = (subjects_value,)
    else:
        subjects = tuple(subjects_value)

    metrics_block = parcellation.get("metrics", {})
    metrics = MetricSelection(
        names=tuple(metrics_block.get("names", ("mean", "median"))),
        connectivity=bool(metrics_block.get("connectivity", False)),
    )

    atlases_block = parcellation.get("atlases", [])
    atlases = [_parse_atlas_entry(item) for item in atlases_block]

    return ParcellationConfig(
        input_root=input_root,
        output_root=output_root,
        subjects=subjects,
        atlases=atlases,
        metrics=metrics,
        profile=parcellation.get("profile", "volume"),
        extra=parcellation.get("extra", {}),
    )
