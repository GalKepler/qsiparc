"""Discover QSIRecon output files using BIDS-like glob patterns.

This module is the sole interface between QSIParc and the filesystem layout
of QSIRecon derivatives. All path assumptions live here — the rest of the
package works with resolved file paths and parsed entities.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from qsiparc.atlas import AtlasLUT, load_lut_from_dseg, load_lut_from_tsv

logger = logging.getLogger(__name__)

# Regex for extracting BIDS-style key-value entities from filenames.
# Matches patterns like "sub-001", "ses-pre", "seg-Schaefer100", "model-DKI", etc.
_ENTITY_RE = re.compile(r"(?P<key>[a-zA-Z]+)-(?P<val>[a-zA-Z0-9]+)")


def sanitize_participant_label(participant_label: str) -> str:
    """Sanitize a participant label to ensure it has the "sub-" prefix.

    Args:
        participant_label (str): Participant label, with or without "sub-" prefix.

    Returns:
        str: Participant label with "sub-" prefix.
    """
    return (
        participant_label
        if participant_label.startswith("sub-")
        else f"sub-{participant_label}"
    )


def sanitize_session_label(session_label: str) -> str:
    """Sanitize a session label to ensure it has the "ses-" prefix.

    Args:
        session_label (str): Session label, with or without "ses-" prefix.

    Returns:
        str: Session label with "ses-" prefix.
    """
    return session_label if session_label.startswith("ses-") else f"ses-{session_label}"


def parse_entities(filename: str) -> dict[str, str]:
    """Extract BIDS key-value pairs from a filename stem.

    Parameters
    ----------
    filename : str
        Filename (with or without extension) to parse.

    Returns
    -------
    dict[str, str]
        Mapping of entity keys to values, e.g. {"sub": "001", "ses": "pre"}.
    """
    return {m.group("key"): m.group("val") for m in _ENTITY_RE.finditer(filename)}


@dataclass(frozen=True)
class BIDSFile:
    """A discovered file with its parsed BIDS entities."""

    path: Path
    entities: dict[str, str] = field(default_factory=dict)

    @property
    def subject(self) -> str:
        return self.entities.get("sub", "")

    @property
    def session(self) -> str:
        return self.entities.get("ses", "")

    @property
    def atlas(self) -> str:
        # Real QSIRecon uses seg- entity; older fixtures may use atlas-
        return self.entities.get("seg", self.entities.get("atlas", ""))

    @property
    def software(self) -> str:
        """Extract the QSIRecon workflow name from the path.

        Returns the suffix after ``qsirecon-`` in the workflow directory
        component of the path (e.g. ``"AMICONODDI"`` from
        ``derivatives/qsirecon-AMICONODDI/...``). Returns an empty string
        if the path does not pass through a ``qsirecon-*`` directory.
        """
        for part in self.path.parts:
            if part.startswith("qsirecon-"):
                return part[len("qsirecon-"):].replace("_", "").replace("-", "")
        return ""


@dataclass(frozen=True)
class AtlasDsegFile:
    """A subject-space atlas dseg NIfTI paired with its atlas LUT.

    Parameters
    ----------
    path : Path
        Subject-space dseg NIfTI (already in subject diffusion space).
    entities : dict[str, str]
        Parsed BIDS entities from the filename.
    atlas_name : str
        Value of the ``seg`` entity (e.g. ``"AAL116"``).
    lut_path : Path or None
        Path to the atlas TSV in ``<qsirecon_dir>/atlases/``, or None if not found.
    """

    path: Path
    entities: dict[str, str]
    atlas_name: str
    lut_path: Path | None

    @property
    def subject(self) -> str:
        return self.entities.get("sub", "")

    @property
    def session(self) -> str:
        return self.entities.get("ses", "")


def find_atlas_lut(qsirecon_dir: Path, atlas_name: str) -> Path | None:
    """Find the LUT TSV for a named atlas in the qsirecon atlases directory.

    QSIRecon ships atlas label files at::

        <qsirecon_dir>/atlases/atlas-{name}/{name}_dseg.tsv

    Parameters
    ----------
    qsirecon_dir : Path
        Root of the QSIRecon derivatives tree.
    atlas_name : str
        Atlas name matching the seg entity (e.g. ``"AAL116"``).

    Returns
    -------
    Path or None
        Path to the ``*_dseg.tsv`` file, or None if not found.
    """
    atlas_dir = qsirecon_dir / "atlases" / f"atlas-{atlas_name}"
    if not atlas_dir.is_dir():
        logger.debug("Atlas directory not found: %s", atlas_dir)
        return None
    candidates = sorted(atlas_dir.glob("*_dseg.tsv"))
    if not candidates:
        logger.debug("No *_dseg.tsv found in %s", atlas_dir)
        return None
    return candidates[0]


def load_lut_for_dseg(dseg_file: AtlasDsegFile) -> AtlasLUT:
    """Load the atlas LUT for a discovered dseg file.

    Uses the paired ``lut_path`` if available, otherwise falls back to
    extracting unique labels directly from the NIfTI.

    Parameters
    ----------
    dseg_file : AtlasDsegFile
        Discovered dseg with optional ``lut_path``.

    Returns
    -------
    AtlasLUT
    """
    if dseg_file.lut_path is not None and dseg_file.lut_path.exists():
        logger.info("Loading LUT from %s", dseg_file.lut_path)
        return load_lut_from_tsv(dseg_file.lut_path, atlas_name=dseg_file.atlas_name)
    logger.warning(
        "No LUT file found for atlas %s — falling back to dseg labels",
        dseg_file.atlas_name,
    )
    return load_lut_from_dseg(dseg_file.path, atlas_name=dseg_file.atlas_name)


def discover_dseg_files(
    qsirecon_dir: Path,
    participant_label: str | None = None,
    session_label: str | None = None,
    atlas: str | None = None,
) -> list[AtlasDsegFile]:
    """Find atlas parcellation (dseg) NIfTIs in a QSIRecon derivatives directory.

    Parameters
    ----------
    qsirecon_dir : Path
        Root of the QSIRecon derivatives tree.
    participant_label : str, optional
        Restrict to a single subject (e.g. ``"sub-001"`` or ``"001"``).
    session_label : str, optional
        Restrict to a single session (e.g. ``"ses-01"`` or ``"01"``).
    atlas : str, optional
        Restrict to a single atlas name (e.g. ``"Schaefer2018N100Tian2020S2"``).

    Returns
    -------
    list[AtlasDsegFile]
        Discovered dseg files with parsed entities and paired atlas LUT paths.
    """
    sub_pattern = (
        sanitize_participant_label(participant_label) if participant_label else "sub-*"
    )
    ses_pattern = (
        sanitize_session_label(session_label) if session_label else "ses-*"
    )

    glob_pattern = f"{sub_pattern}/{ses_pattern}/dwi/*_dseg.nii.gz"
    results = []

    for path in sorted(qsirecon_dir.glob(glob_pattern)):
        entities = parse_entities(path.name)
        atlas_name = entities.get("seg", "")
        if not atlas_name:
            continue  # skip dsegs without a seg entity
        if atlas and atlas_name != atlas:
            continue
        lut_path = find_atlas_lut(qsirecon_dir, atlas_name)
        results.append(
            AtlasDsegFile(
                path=path,
                entities=entities,
                atlas_name=atlas_name,
                lut_path=lut_path,
            )
        )

    logger.info(
        "Discovered %d dseg files (filters: participant=%s, session=%s, atlas=%s)",
        len(results),
        participant_label,
        session_label,
        atlas,
    )
    return results


def discover_scalar_maps(
    qsirecon_dir: Path,
    subject: str,
    session: str,
    scalars: list[str] | None = None,
) -> list[BIDSFile]:
    """Find diffusion scalar map NIfTIs for a given subject/session.

    Searches all ``derivatives/qsirecon-*`` workflow subdirectories for
    ``*.nii.gz`` files that are neither dsegs nor preprocessed DWI.

    Parameters
    ----------
    qsirecon_dir : Path
        Root of the QSIRecon derivatives tree.
    subject : str
        Subject label (with or without ``sub-`` prefix).
    session : str
        Session label (with or without ``ses-`` prefix).
    scalars : list[str], optional
        If provided, only return maps whose ``param`` entity (or filename stem)
        contains one of these scalar names (case-insensitive).

    Returns
    -------
    list[BIDSFile]
        Discovered scalar map files.
    """
    subject = sanitize_participant_label(subject)
    session = sanitize_session_label(session)
    derivatives_dir = qsirecon_dir / "derivatives"
    if not derivatives_dir.is_dir():
        logger.warning("Derivatives directory not found: %s", derivatives_dir)
        return []

    results = []
    for workflow_dir in sorted(derivatives_dir.glob("qsirecon-*")):
        dwi_dir = workflow_dir / subject / session / "dwi"
        if not dwi_dir.is_dir():
            continue
        for path in sorted(dwi_dir.glob("*_dwimap.nii.gz")):
            if "_dseg" in path.name:
                continue
            entities = parse_entities(path.name)
            if entities.get("space") != "ACPC":
                continue
            if scalars:
                param = entities.get("param", entities.get("desc", ""))
                stem_lower = path.stem.lower()
                if not any(
                    s.lower() in param.lower() or s.lower() in stem_lower
                    for s in scalars
                ):
                    continue
            results.append(BIDSFile(path=path, entities=entities))

    logger.info(
        "Discovered %d scalar maps for %s/%s (filter: %s)",
        len(results),
        subject,
        session,
        scalars,
    )
    return results


def discover_tractography(
    qsirecon_dir: Path,
    subject: str,
    session: str,
) -> list[BIDSFile]:
    """Find tractography files (.tck.gz) for a given subject/session.

    Parameters
    ----------
    qsirecon_dir : Path
        Root of the QSIRecon derivatives tree.
    subject : str
        Subject label (with or without ``sub-`` prefix).
    session : str
        Session label (with or without ``ses-`` prefix).

    Returns
    -------
    list[BIDSFile]
        Discovered tractography files (``*_streamlines.tck.gz``).
    """
    subject = sanitize_participant_label(subject)
    session = sanitize_session_label(session)
    derivatives_dir = qsirecon_dir / "derivatives"
    if not derivatives_dir.is_dir():
        return []

    results = []
    for workflow_dir in sorted(derivatives_dir.glob("qsirecon-*")):
        dwi_dir = workflow_dir / subject / session / "dwi"
        if not dwi_dir.is_dir():
            continue
        for path in sorted(dwi_dir.glob("*_streamlines.tck.gz")):
            results.append(BIDSFile(path=path, entities=parse_entities(path.name)))

    logger.info(
        "Discovered %d tractography files for %s/%s",
        len(results),
        subject,
        session,
    )
    return results


def discover_sift_weights(
    qsirecon_dir: Path,
    subject: str,
    session: str,
) -> list[BIDSFile]:
    """Find SIFT2 streamline weight files for a given subject/session.

    Parameters
    ----------
    qsirecon_dir : Path
        Root of the QSIRecon derivatives tree.
    subject : str
        Subject label (with or without ``sub-`` prefix).
    session : str
        Session label (with or without ``ses-`` prefix).

    Returns
    -------
    list[BIDSFile]
        Discovered SIFT2 weight CSV files (``*_streamlineweights.csv``).
    """
    subject = sanitize_participant_label(subject)
    session = sanitize_session_label(session)
    derivatives_dir = qsirecon_dir / "derivatives"
    if not derivatives_dir.is_dir():
        return []

    results = []
    for workflow_dir in sorted(derivatives_dir.glob("qsirecon-*")):
        dwi_dir = workflow_dir / subject / session / "dwi"
        if not dwi_dir.is_dir():
            continue
        for path in sorted(dwi_dir.glob("*_streamlineweights.csv")):
            results.append(BIDSFile(path=path, entities=parse_entities(path.name)))

    logger.info(
        "Discovered %d SIFT2 weight files for %s/%s",
        len(results),
        subject,
        session,
    )
    return results
