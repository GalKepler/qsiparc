"""Aggregate per-subject QSIParc outputs into group-level long-format tables.

This module discovers and reads back diffmap TSVs and connectome CSVs produced
by a previous qsiparc run, then concatenates them across subjects and sessions.

Output layout (written by the ``aggregate`` CLI command)::

    <out_dir>/
        atlas-<name>/
            atlas-<name>_workflow-<wf>_param-<scalar>_diffmap.tsv
            atlas-<name>_desc-<measure>_connmatrix.tsv

One output file is produced for each unique combination of atlas, workflow,
scalar, and any other BIDS entities — with subject and session becoming row
identifiers in the long-format table.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from qsiparc.discover import BIDSFile, parse_entities

logger = logging.getLogger(__name__)

_SUB_SES_RE = re.compile(r"^sub-[^_]+_ses-[^_]+_")


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_diffmap_tsvs(
    qsiparc_dir: Path,
    atlas: list[str] | None = None,
) -> list[BIDSFile]:
    """Discover all diffmap TSV files under a qsiparc output directory.

    Parameters
    ----------
    qsiparc_dir:
        Root of a qsiparc output directory (contains sub-*/ses-*/ subdirs).
    atlas:
        If provided, only files belonging to one of these atlas names are
        returned.  Matching is done on the ``atlas`` BIDS entity in the
        filename.

    Returns
    -------
    list[BIDSFile]
        Discovered files, sorted for reproducibility.
    """
    files = sorted(qsiparc_dir.glob("sub-*/ses-*/dwi/atlas-*/*_diffmap.tsv"))
    result: list[BIDSFile] = []
    for path in files:
        entities = parse_entities(path.name)
        if atlas and entities.get("atlas") not in atlas:
            continue
        result.append(BIDSFile(path=path, entities=entities))
    logger.debug("discover_diffmap_tsvs: found %d file(s)", len(result))
    return result


def discover_connmatrix_csvs(
    qsiparc_dir: Path,
    atlas: list[str] | None = None,
) -> list[BIDSFile]:
    """Discover all connmatrix CSV files under a qsiparc output directory.

    Each CSV is expected to have a paired ``*_connmatrix.json`` sidecar at the
    same path with ``.json`` extension.

    Parameters
    ----------
    qsiparc_dir:
        Root of a qsiparc output directory.
    atlas:
        If provided, only files belonging to one of these atlas names are
        returned.

    Returns
    -------
    list[BIDSFile]
        Discovered files, sorted for reproducibility.
    """
    files = sorted(qsiparc_dir.glob("sub-*/ses-*/dwi/atlas-*/*_connmatrix.csv"))
    result: list[BIDSFile] = []
    for path in files:
        entities = parse_entities(path.name)
        if atlas and entities.get("atlas") not in atlas:
            continue
        result.append(BIDSFile(path=path, entities=entities))
    logger.debug("discover_connmatrix_csvs: found %d file(s)", len(result))
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _group_key(path: Path) -> str:
    """Derive the output filename stem by stripping the sub/ses prefix.

    Given a per-subject filename like::

        sub-001_ses-01_atlas-TestAtlas5_software-DTI_param-FA_diffmap.tsv

    returns::

        atlas-TestAtlas5_software-DTI_param-FA_diffmap

    This string uniquely identifies the atlas/workflow/scalar/entity
    combination and is used both as the grouping key and as the output
    filename stem.
    """
    return _SUB_SES_RE.sub("", path.stem)


def _atlas_from_key(key: str) -> str:
    """Extract the atlas name from a group key string."""
    return parse_entities(key).get("atlas", "unknown")


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate_diffmaps(
    diffmap_files: list[BIDSFile],
) -> dict[str, pd.DataFrame]:
    """Read and concatenate diffmap TSVs, grouped by entity fingerprint.

    Files are grouped by everything in their filename *except* subject and
    session — so one output table is produced per unique combination of atlas,
    workflow, scalar map, and any other BIDS entities.  Subject and session
    become row-identifier columns prepended to the table.

    Parameters
    ----------
    diffmap_files:
        List of BIDSFile objects pointing to ``*_diffmap.tsv`` files.

    Returns
    -------
    dict[str, pd.DataFrame]
        Mapping of group key → concatenated long-format DataFrame.  The group
        key is the output filename stem (e.g.
        ``atlas-TestAtlas5_software-DTI_param-FA_diffmap``).  Columns:
        ``subject, session, region_index, region_name, hemisphere, scalar,
        mean, median, std, iqr, skewness, kurtosis, n_voxels, coverage``.
    """
    grouped: dict[str, list[pd.DataFrame]] = defaultdict(list)

    for bf in diffmap_files:
        entities = bf.entities
        subject = f"sub-{entities.get('sub', '')}"
        session = f"ses-{entities.get('ses', '')}"
        key = _group_key(bf.path)

        try:
            df = pd.read_csv(bf.path, sep="\t")
        except Exception as exc:
            logger.warning("Could not read %s: %s — skipping", bf.path, exc)
            continue

        df.insert(0, "subject", subject)
        df.insert(1, "session", session)

        grouped[key].append(df)
        logger.debug(
            "aggregate_diffmaps: read %d rows from %s/%s key=%s",
            len(df),
            subject,
            session,
            key,
        )

    return {key: pd.concat(dfs, ignore_index=True) for key, dfs in grouped.items()}


def aggregate_connectomes(
    connmatrix_files: list[BIDSFile],
    include_diagonal: bool = False,
) -> dict[str, pd.DataFrame]:
    """Read and concatenate connectome matrices as long-format edge lists.

    Files are grouped by their entity fingerprint (everything except subject
    and session), so one output table is produced per unique atlas/measure
    combination.  Each symmetric NxN matrix is flattened to the upper
    triangle (optionally including the diagonal).  Region labels are taken
    from the paired JSON sidecar.

    Parameters
    ----------
    connmatrix_files:
        List of BIDSFile objects pointing to ``*_connmatrix.csv`` files.
    include_diagonal:
        If True, include self-connections (i == j) in the edge list.
        Default: False.

    Returns
    -------
    dict[str, pd.DataFrame]
        Mapping of group key → concatenated edge-list DataFrame.  The group
        key is the output filename stem (e.g.
        ``atlas-TestAtlas5_desc-sift_invnodevol_radius2_count_connmatrix``).
        Columns: ``subject, session, region_i_index, region_j_index,
        region_i_name, region_j_name, weight``.
    """
    grouped: dict[str, list[pd.DataFrame]] = defaultdict(list)

    for bf in connmatrix_files:
        json_path = bf.path.with_suffix(".json")
        if not json_path.exists():
            logger.warning(
                "No JSON sidecar for %s — cannot determine region labels." " Skipping.",
                bf.path.name,
            )
            continue

        try:
            with open(json_path) as fh:
                sidecar = json.load(fh)
        except Exception as exc:
            logger.warning("Could not read sidecar %s: %s — skipping", json_path, exc)
            continue

        try:
            matrix = np.loadtxt(bf.path, delimiter=",")
        except Exception as exc:
            logger.warning("Could not read matrix %s: %s — skipping", bf.path, exc)
            continue

        entities = bf.entities
        subject = f"sub-{entities.get('sub', '')}"
        session = f"ses-{entities.get('ses', '')}"
        key = _group_key(bf.path)
        labels: list[str] = sidecar.get("region_labels", [])
        n = matrix.shape[0]

        rows: list[dict] = []
        for i in range(n):
            j_start = i if include_diagonal else i + 1
            for j in range(j_start, n):
                rows.append(
                    {
                        "subject": subject,
                        "session": session,
                        "region_i_index": i + 1,
                        "region_j_index": j + 1,
                        "region_i_name": labels[i]
                        if i < len(labels)
                        else f"region_{i + 1}",
                        "region_j_name": labels[j]
                        if j < len(labels)
                        else f"region_{j + 1}",
                        "weight": matrix[i, j],
                    }
                )

        edge_df = pd.DataFrame(rows)
        grouped[key].append(edge_df)
        logger.debug(
            "aggregate_connectomes: %d edges from %s/%s key=%s",
            len(edge_df),
            subject,
            session,
            key,
        )

    return {key: pd.concat(dfs, ignore_index=True) for key, dfs in grouped.items()}


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------


def write_aggregate_tsv(df: pd.DataFrame, output_path: Path) -> Path:
    """Write a DataFrame to a tab-separated file, creating parent directories.

    Parameters
    ----------
    df:
        DataFrame to write.
    output_path:
        Destination file path.

    Returns
    -------
    Path
        The path that was written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, sep="\t", index=False)
    return output_path
