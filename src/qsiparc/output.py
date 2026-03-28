"""Output writing: BIDS-derivative layout for parcellated diffusion features.

Handles:
- Creating the output directory structure
- Writing long-format TSV files with consistent column ordering
- Writing dataset_description.json for BIDS compliance
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Canonical column order for diffmap TSVs
DIFFMAP_COLUMNS = [
    "region_index",
    "region_name",
    "hemisphere",
    "structure",
    "scalar",
    "mean",
    "median",
    "std",
    "iqr",
    "skewness",
    "kurtosis",
    "n_voxels",
    "coverage",
]


def write_diffmap_tsv(
    df: pd.DataFrame,
    output_dir: Path,
    subject: str,
    session: str,
    atlas_name: str,
    source_entities: dict[str, str] | None = None,
) -> Path:
    """Write a parcellated diffusion scalar map as a BIDS-derivative TSV.

    Output path:
        <output_dir>/sub-xxx/ses-yyy/dwi/atlas-<atlas_name>/
            sub-xxx_ses-yyy_atlas-<atlas_name>_diffmap.tsv

    Parameters
    ----------
    df : pd.DataFrame
        Long-format DataFrame from `merge_extraction_results`.
    output_dir : Path
        Root of the output derivatives tree.
    subject : str
        Subject label (e.g. "sub-001").
    session : str
        Session label (e.g. "ses-01").
    atlas_name : str
        Atlas name for the directory and filename.
    source_entities : dict, optional
        Additional BIDS entities from the source files to propagate into the filename.

    Returns
    -------
    Path
        Path to the written TSV file.
    """
    atlas_dir = output_dir / subject / session / "dwi" / f"atlas-{atlas_name}"
    atlas_dir.mkdir(parents=True, exist_ok=True)

    # Build filename with optional additional entities
    parts = [subject, session, f"atlas-{atlas_name}"]
    if source_entities:
        for key in ("space", "model", "desc"):
            if key in source_entities:
                parts.append(f"{key}-{source_entities[key]}")
    parts.append("diffmap")
    filename = "_".join(parts) + ".tsv"

    out_path = atlas_dir / filename

    # Enforce column order, keeping only columns that exist
    cols = [c for c in DIFFMAP_COLUMNS if c in df.columns]
    extra_cols = [c for c in df.columns if c not in DIFFMAP_COLUMNS]
    if extra_cols:
        logger.info("Extra columns in output (appended): %s", extra_cols)
        cols.extend(extra_cols)

    df[cols].to_csv(out_path, sep="\t", index=False, float_format="%.6f")
    logger.info("Wrote diffmap TSV (%d rows): %s", len(df), out_path)
    return out_path


def write_dataset_description(output_dir: Path) -> Path:
    """Write a minimal BIDS dataset_description.json to the output root.

    Parameters
    ----------
    output_dir : Path
        Root of the output derivatives tree.

    Returns
    -------
    Path
        Path to the written JSON file.
    """
    desc = {
        "Name": "QSIParc — Parcellated Diffusion Features",
        "BIDSVersion": "1.9.0",
        "DatasetType": "derivative",
        "GeneratedBy": [
            {
                "Name": "QSIParc",
                "Description": "Parcellated diffusion scalar extraction and connectivity repackaging from QSIRecon outputs.",
                "CodeURL": "https://github.com/snbb/qsiparc",
            }
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "dataset_description.json"
    with open(out_path, "w") as f:
        json.dump(desc, f, indent=2)
    logger.info("Wrote dataset_description.json: %s", out_path)
    return out_path
