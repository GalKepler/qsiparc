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

from qsiparc.atlas import AtlasLUT

logger = logging.getLogger(__name__)

# Regex for extracting BIDS-style key-value entities from filenames.
# Matches patterns like "sub-001", "ses-pre", "atlas-Schaefer100", "model-DKI", etc.
_ENTITY_RE = re.compile(r"(?P<key>[a-zA-Z]+)-(?P<val>[a-zA-Z0-9]+)")


def sanitize_participant_label(participant_label: str) -> str:
    return (
        participant_label
        if participant_label.startswith("sub-")
        else f"sub-{participant_label}"
    )


def sanitize_session_label(session_label: str) -> str:
    return session_label if session_label.startswith("ses-") else f"ses-{session_label}"


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
        return self.entities.get("atlas", "")


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


def discover_dseg_files(
    qsirecon_dir: Path,
    participant_label: str | None = None,
    session_label: str | None = None,
    atlas: str | None = None,
) -> list[BIDSFile]:
    """Find atlas parcellation (dseg) files in a QSIRecon derivatives directory.

    Parameters
    ----------
    qsirecon_dir : Path
        Root of the QSIRecon derivatives tree.
    participant_label : str, optional
        Restrict to a single subject (e.g. "sub-001").
    session_label : str, optional
        Restrict to a single session (e.g. "ses-01").
    atlas : str, optional
        Restrict to a single atlas name (e.g. "Schaefer2018N100Tian2020S2").

    Returns
    -------
    list[BIDSFile]
        Discovered dseg files with parsed entities.
    """
    if not participant_label:
        sub_pattern = "sub-*"
    else:
        sub_pattern = sanitize_participant_label(participant_label=participant_label)
    if not session_label:
        ses_pattern = "ses-*"
    else:
        ses_pattern = sanitize_session_label(session_label=session_label)

    glob_pattern = f"{sub_pattern}/{ses_pattern}/dwi/*_dseg.nii.gz"
    results = []

    for path in sorted(qsirecon_dir.glob(glob_pattern)):
        entities = parse_entities(path.name)
        if atlas and entities.get("seg") != atlas:
            continue
        results.append(BIDSFile(path=path, entities=entities))

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

    Scalar maps are expected to have entities like:
        model-{name}_param-{name} or desc-{name}
    in their filename. QSIRecon's naming varies by reconstruction workflow,
    so we glob broadly and let the caller filter.

    Parameters
    ----------
    qsirecon_dir : Path
        Root of the QSIRecon derivatives tree.
    subject : str
        Subject label including prefix, e.g. "sub-001".
    session : str
        Session label including prefix, e.g. "ses-01".
    scalars : list[str], optional
        If provided, only return maps whose filename contains one of these
        scalar names (case-insensitive match against the full filename stem).

    Returns
    -------
    list[BIDSFile]
        Discovered scalar map files.
    """
    subject = sanitize_participant_label(participant_label=subject)
    session = sanitize_session_label(session_label=session)
    derivatives_dir = qsirecon_dir / "derivatives"
    if not derivatives_dir.is_dir():
        logger.warning("DWI derivatives directory not found: %s", derivatives_dir)
        return []

    results = []
    for workflow_dir in sorted(derivatives_dir.glob("qsirecon-*")):
        workflow_name = (
            workflow_dir.name.replace("qsirecon-", "").replace("-", "").replace("_", "")
        )
        dwi_dir = workflow_dir / subject / session / "dwi"
        for path in dwi_dir.glob("*.nii.gz"):
            # Skip parcellations and preprocessed DWI
            if "_dseg" in path.name or "_desc-preproc_dwi" in path.name:
                continue

            entities = parse_entities(path.name)
            entities.update({"workflow": workflow_name})
            if scalars:
                stem_lower = path.stem.lower()
                if not any(s.lower() in stem_lower for s in scalars):
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
