"""Atlas look-up table (LUT) loading and region metadata.

QSIRecon ships atlas label files in several formats. This module provides a
unified interface for loading them into a structured region table that the
rest of QSIParc uses for labeling output rows and columns.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegionInfo:
    """Metadata for a single atlas region."""

    index: int
    name: str
    hemisphere: str  # "L", "R", or "bilateral"


class AtlasLUT:
    """Container for atlas region metadata.

    Parameters
    ----------
    regions : list[RegionInfo]
        Ordered list of region definitions.
    atlas_name : str
        Name of the atlas (e.g. "Schaefer2018N100Tian2020S2").
    """

    def __init__(self, regions: list[RegionInfo], atlas_name: str = "") -> None:
        self.regions = regions
        self.atlas_name = atlas_name
        self._index_map = {r.index: r for r in regions}

    def __len__(self) -> int:
        return len(self.regions)

    def __getitem__(self, index: int) -> RegionInfo:
        return self._index_map[index]

    def get(self, index: int, default: RegionInfo | None = None) -> RegionInfo | None:
        return self._index_map.get(index, default)

    @property
    def indices(self) -> list[int]:
        """Sorted list of all region indices."""
        return sorted(self._index_map.keys())

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to a DataFrame for merging with extraction results."""
        return pd.DataFrame(
            [
                {
                    "region_index": r.index,
                    "region_name": r.name,
                    "hemisphere": r.hemisphere,
                }
                for r in self.regions
            ]
        )


def infer_hemisphere(name: str) -> str:
    """Guess hemisphere from a region name string.

    Uses common neuroimaging naming conventions:
    - Prefix or suffix "LH", "lh", "Left", "L_" → "L"
    - Prefix or suffix "RH", "rh", "Right", "R_" → "R"
    - Otherwise → "bilateral"
    """
    lower = name.lower()
    # Check common prefixes/suffixes
    if any(
        lower.startswith(p) for p in ("lh_", "lh-", "lh.", "left_", "left-", "l_")
    ) or any(lower.endswith(s) for s in ("_lh", "-lh", "_left", "-left", "_l")):
        return "L"
    if any(
        lower.startswith(p) for p in ("rh_", "rh-", "rh.", "right_", "right-", "r_")
    ) or any(lower.endswith(s) for s in ("_rh", "-rh", "_right", "-right", "_r")):
        return "R"
    # Schaefer-style: "7Networks_LH_Vis_1" or "17Networks_RH_Default_1"
    if "_lh_" in lower or "_LH_" in name:
        return "L"
    if "_rh_" in lower or "_RH_" in name:
        return "R"
    return "bilateral"


def load_lut_from_tsv(path: Path, atlas_name: str = "") -> AtlasLUT:
    """Load a TSV LUT file (common QSIRecon format).

    Expected columns: index, name (minimum). Optional: hemisphere.
    Also handles FreeSurfer-style LUT format (index name R G B A).

    Parameters
    ----------
    path : Path
        Path to the TSV/text LUT file.
    atlas_name : str
        Atlas name for metadata.

    Returns
    -------
    AtlasLUT
    """
    # Try pandas first for well-formed TSVs
    try:
        df = pd.read_csv(path, sep=r"\t", engine="python")
    except Exception:
        # Fall back to manual parsing for FreeSurfer-style LUTs
        return _parse_freesurfer_lut(path, atlas_name)

    # Normalize column names
    df.columns = [str(c).lower().strip() for c in df.columns]

    # Identify index and name columns.
    # "label" is a name candidate (QSIRecon atlas TSVs use index + label columns).
    idx_col = next(
        (c for c in df.columns if c in ("index", "id", "region_id")),
        df.columns[0],
    )
    name_col = next(
        (c for c in df.columns if c in ("name", "label", "region", "label_name", "region_name")),
        df.columns[1],
    )

    regions = []
    for _, row in df.iterrows():
        idx = int(row[idx_col])
        if idx == 0:
            continue  # Skip background
        name = str(row[name_col])
        hemisphere = row.get("hemisphere", infer_hemisphere(name))
        regions.append(
            RegionInfo(index=idx, name=name, hemisphere=hemisphere)
        )

    logger.info("Loaded %d regions from TSV LUT: %s", len(regions), path)
    return AtlasLUT(regions=regions, atlas_name=atlas_name)


def load_lut_from_json(path: Path, atlas_name: str = "") -> AtlasLUT:
    """Load a JSON LUT file.

    Expected format: {"1": "RegionName", "2": "RegionName", ...}
    or: [{"index": 1, "name": "...", ...}, ...]
    """
    with open(path) as f:
        data = json.load(f)

    regions = []
    if isinstance(data, dict):
        for idx_str, name in data.items():
            idx = int(idx_str)
            if idx == 0:
                continue
            regions.append(
                RegionInfo(
                    index=idx,
                    name=name,
                    hemisphere=infer_hemisphere(name),                )
            )
    elif isinstance(data, list):
        for entry in data:
            idx = int(entry.get("index", entry.get("id", 0)))
            if idx == 0:
                continue
            name = entry.get("name", entry.get("label", f"region_{idx}"))
            regions.append(
                RegionInfo(
                    index=idx,
                    name=name,
                    hemisphere=entry.get("hemisphere", infer_hemisphere(name)),
                )
            )

    logger.info("Loaded %d regions from JSON LUT: %s", len(regions), path)
    return AtlasLUT(regions=regions, atlas_name=atlas_name)


def load_lut_from_dseg(dseg_path: Path, atlas_name: str = "") -> AtlasLUT:
    """Create a minimal LUT from a dseg NIfTI when no label file is available.

    Extracts unique non-zero integer labels and assigns generic names.
    This is a fallback — prefer loading a proper LUT file.
    """
    import nibabel as nib

    img = nib.load(dseg_path)
    data = np.asarray(img.dataobj, dtype=np.int32)
    unique_labels = sorted(set(data.ravel()) - {0})

    regions = [
        RegionInfo(
            index=int(idx),
            name=f"region_{idx:04d}",
            hemisphere="bilateral",
        )
        for idx in unique_labels
    ]
    logger.warning(
        "Created fallback LUT from dseg with %d regions (no label names): %s",
        len(regions),
        dseg_path,
    )
    return AtlasLUT(regions=regions, atlas_name=atlas_name)


def _parse_freesurfer_lut(path: Path, atlas_name: str) -> AtlasLUT:
    """Parse FreeSurfer-style LUT: index name R G B A."""
    regions = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                idx = int(parts[0])
            except ValueError:
                continue
            if idx == 0:
                continue
            name = parts[1]
            regions.append(
                RegionInfo(
                    index=idx,
                    name=name,
                    hemisphere=infer_hemisphere(name),
                )
            )
    logger.info("Loaded %d regions from FreeSurfer LUT: %s", len(regions), path)
    return AtlasLUT(regions=regions, atlas_name=atlas_name)
