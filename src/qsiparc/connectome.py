"""Connectome passthrough: read, validate, and repackage QSIRecon connectivity matrices.

QSIRecon already computes structural connectivity matrices from tractography.
QSIParc does not recompute them — it reads the CSV outputs, validates them,
and writes them to the BIDS-derivative output layout with JSON sidecar metadata.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from qsiparc.atlas import AtlasLUT
from qsiparc.discover import BIDSFile, parse_entities

logger = logging.getLogger(__name__)


@dataclass
class ConnectomeResult:
    """A validated connectivity matrix with metadata."""

    matrix: np.ndarray  # shape (N, N)
    atlas_name: str
    edge_weight: str  # "streamline_count", "mean_length", "sift2", "fa_weighted", etc.
    region_labels: list[str]
    source_file: Path
    entities: dict[str, str]


def infer_edge_weight(bids_file: BIDSFile) -> str:
    """Infer the edge weight type from the filename entities.

    QSIRecon encodes this in various ways depending on the reconstruction spec.
    Common patterns:
        *_algo-CSD_atlas-*_connectivity.csv → streamline_count
        *_algo-CSD_atlas-*_desc-sift2_connectivity.csv → sift2_weighted
        *_algo-CSD_atlas-*_desc-meanlength_connectivity.csv → mean_length
    """
    entities = bids_file.entities
    desc = entities.get("desc", "").lower()
    measure = entities.get("measure", "").lower()

    if "sift2" in desc or "sift2" in measure:
        return "sift2_weighted"
    if "meanlength" in desc or "length" in measure:
        return "mean_length"
    if "fa" in desc:
        return "fa_weighted"
    if "md" in desc:
        return "md_weighted"
    # Default for undecorated connectivity files
    return "streamline_count"


def load_connectome(
    bids_file: BIDSFile,
    lut: AtlasLUT | None = None,
) -> ConnectomeResult:
    """Load and validate a QSIRecon connectivity CSV.

    Parameters
    ----------
    bids_file : BIDSFile
        Discovered connectome file.
    lut : AtlasLUT, optional
        If provided, validates matrix dimensions against the atlas.

    Returns
    -------
    ConnectomeResult

    Raises
    ------
    ValueError
        If the matrix is not square or doesn't match the atlas.
    """
    path = bids_file.path

    # QSIRecon outputs vary: some have headers, some don't. Try both.
    try:
        matrix = np.loadtxt(path, delimiter=",")
    except ValueError:
        # Retry skipping first row (header)
        matrix = np.loadtxt(path, delimiter=",", skiprows=1)

    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError(
            f"Connectivity matrix is not square: shape {matrix.shape} in {path}"
        )

    n_regions = matrix.shape[0]

    if lut is not None and len(lut) != n_regions:
        raise ValueError(
            f"Matrix has {n_regions} regions but atlas LUT has {len(lut)} regions. "
            f"File: {path}, Atlas: {lut.atlas_name}"
        )

    region_labels = [r.name for r in lut.regions] if lut else [f"region_{i+1}" for i in range(n_regions)]
    edge_weight = infer_edge_weight(bids_file)

    logger.info(
        "Loaded %dx%d connectome (edge_weight=%s) from %s",
        n_regions,
        n_regions,
        edge_weight,
        path,
    )

    return ConnectomeResult(
        matrix=matrix,
        atlas_name=bids_file.atlas,
        edge_weight=edge_weight,
        region_labels=region_labels,
        source_file=path,
        entities=bids_file.entities,
    )


def write_connectome(
    result: ConnectomeResult,
    output_dir: Path,
    subject: str,
    session: str,
) -> tuple[Path, Path]:
    """Write a connectome to the BIDS-derivative output layout.

    Produces:
    - A square CSV matrix (no headers, region order matches LUT)
    - A JSON sidecar with metadata

    Parameters
    ----------
    result : ConnectomeResult
        Validated connectome.
    output_dir : Path
        Root of the output derivatives tree.
    subject : str
        Subject label (e.g. "sub-001").
    session : str
        Session label (e.g. "ses-01").

    Returns
    -------
    tuple[Path, Path]
        Paths to the written CSV and JSON files.
    """
    atlas_dir = output_dir / subject / session / "dwi" / f"atlas-{result.atlas_name}"
    atlas_dir.mkdir(parents=True, exist_ok=True)

    stem = f"{subject}_{session}_atlas-{result.atlas_name}_desc-{result.edge_weight}_connmatrix"
    csv_path = atlas_dir / f"{stem}.csv"
    json_path = atlas_dir / f"{stem}.json"

    np.savetxt(csv_path, result.matrix, delimiter=",", fmt="%.6f")

    sidecar = {
        "atlas_name": result.atlas_name,
        "edge_weight": result.edge_weight,
        "n_regions": int(result.matrix.shape[0]),
        "region_labels": result.region_labels,
        "symmetric": bool(np.allclose(result.matrix, result.matrix.T, atol=1e-8)),
        "source_file": str(result.source_file),
        "source_entities": result.entities,
    }
    with open(json_path, "w") as f:
        json.dump(sidecar, f, indent=2)

    logger.info("Wrote connectome: %s", csv_path)
    return csv_path, json_path
