"""Output writing: BIDS-derivative layout for parcellated diffusion features.

Handles:
- Creating the output directory structure
- Writing long-format TSV files with consistent column ordering
- Writing JSON sidecar metadata alongside every TSV output
- Writing dataset_description.json for BIDS compliance

JSON sidecar schema (diffmap)
------------------------------
Every ``*_diffmap.tsv`` is accompanied by a ``*_diffmap.json`` that records
the full provenance for that file.  Fields:

subject : str
    BIDS subject label (e.g. ``"sub-001"``).
session : str
    BIDS session label (e.g. ``"ses-01"``).
atlas_name : str
    Atlas used for parcellation (e.g. ``"Schaefer2018N100Tian2020S2"``).
atlas_dseg : str
    Absolute path to the subject-space atlas dseg NIfTI consumed by QSIParc.
lut_file : str or null
    Absolute path to the atlas TSV look-up table, or null when not found and
    labels were inferred directly from the dseg.
scalar_name : str
    Name of the diffusion scalar extracted (e.g. ``"FA"``, ``"ICVF"``).
source_file : str
    Absolute path to the scalar map NIfTI used as input.
source_entities : dict[str, str]
    BIDS key-value entities parsed from the source scalar filename.
software : str or null
    QSIRecon workflow name, taken from the ``qsirecon-*`` directory component
    of the source path (e.g. ``"AMICONODDI"``).  Null when not applicable.
processing : dict
    Parameters that governed the extraction step.  All keys are stable; new
    parameters may be added in future versions.

    zero_is_missing : bool
        Whether voxel values of exactly 0.0 were treated as missing signal
        (NaN) before computing statistics.
    stat_tier : str
        Statistic tier passed to the parcellator (``"extended"`` by default).
    statistics : list[str]
        Ordered list of statistic columns present in the TSV.
generated_by : dict
    Provenance block.

    name : str
        Always ``"QSIParc"``.
    version : str
        Package version string at the time of generation.
    timestamp : str
        ISO-8601 UTC timestamp of when the file was written.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import qsiparc

logger = logging.getLogger(__name__)


@dataclass
class DiffmapProvenance:
    """Provenance metadata for a single diffmap TSV output.

    Construct one instance per ``write_diffmap_tsv`` call and pass it in.
    All path-typed fields accept ``Path`` objects or strings; they are
    serialised as absolute string paths in the JSON sidecar.

    Parameters
    ----------
    subject : str
        BIDS subject label (e.g. ``"sub-001"``).
    session : str
        BIDS session label (e.g. ``"ses-01"``).
    atlas_name : str
        Atlas name (e.g. ``"Schaefer2018N100Tian2020S2"``).
    atlas_dseg : Path or str
        Path to the subject-space atlas dseg NIfTI.
    scalar_name : str
        Name of the diffusion scalar (e.g. ``"FA"``).
    source_file : Path or str
        Path to the scalar map NIfTI.
    lut_file : Path, str, or None
        Path to the atlas look-up table TSV, or None.
    source_entities : dict[str, str]
        BIDS entities from the source scalar filename.
    software : str or None
        QSIRecon workflow name extracted from the source path.
    zero_is_missing : bool
        Whether zeros were treated as NaN during extraction.
    stat_tier : str
        Statistic tier passed to the parcellator (default ``"extended"``).
    """

    subject: str
    session: str
    atlas_name: str
    atlas_dseg: Path | str
    scalar_name: str
    source_file: Path | str
    lut_file: Path | str | None = None
    source_entities: dict[str, str] = field(default_factory=dict)
    software: str | None = None
    zero_is_missing: bool = False
    stat_tier: str = "extended"

    def to_dict(self) -> dict:
        """Serialise to a plain dict suitable for JSON output."""
        return {
            "subject": self.subject,
            "session": self.session,
            "atlas_name": self.atlas_name,
            "atlas_dseg": str(Path(self.atlas_dseg).resolve()),
            "lut_file": str(Path(self.lut_file).resolve()) if self.lut_file else None,
            "scalar_name": self.scalar_name,
            "source_file": str(Path(self.source_file).resolve()),
            "source_entities": self.source_entities,
            "software": self.software or None,
            "processing": {
                "zero_is_missing": self.zero_is_missing,
                "stat_tier": self.stat_tier,
            },
            "generated_by": {
                "name": "QSIParc",
                "version": qsiparc.__version__,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


def write_diffmap_tsv(
    df: pd.DataFrame,
    output_dir: Path,
    subject: str,
    session: str,
    atlas_name: str,
    provenance: DiffmapProvenance | None = None,
    software: str | None = None,
    source_entities: dict[str, str] | None = None,
) -> Path:
    """Write a parcellated diffusion scalar map as a BIDS-derivative TSV.

    A JSON sidecar with the same stem is always written alongside the TSV.
    Pass a :class:`DiffmapProvenance` instance to populate it with full
    extraction provenance.  If *provenance* is omitted a minimal sidecar is
    written using only the arguments available at call time.

    Output path::

        <output_dir>/sub-xxx/ses-yyy/dwi/atlas-<atlas_name>/
            sub-xxx_ses-yyy_atlas-<atlas_name>_software-<software>_\\
            <source_entities>_diffmap.tsv
            sub-xxx_ses-yyy_atlas-<atlas_name>_software-<software>_\\
            <source_entities>_diffmap.json   ← sidecar

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
    provenance : DiffmapProvenance, optional
        Full extraction provenance written to the JSON sidecar.  When
        provided, *software* and *source_entities* are ignored in favour of
        the values already encoded in *provenance*.
    software : str, optional
        QSIRecon workflow name (e.g. ``"AMICONODDI"``).  Used for filename
        construction when *provenance* is not supplied.
    source_entities : dict, optional
        BIDS entities from the source scalar map, forwarded into the filename.
        ``sub`` and ``ses`` are skipped (already encoded in the prefix).
        Used for filename construction when *provenance* is not supplied.

    Returns
    -------
    Path
        Path to the written TSV file.
    """
    # Resolve software / source_entities from provenance if provided
    _software = provenance.software if provenance is not None else software
    _source_entities = (
        provenance.source_entities if provenance is not None else source_entities
    )

    atlas_dir = output_dir / subject / session / "dwi" / f"atlas-{atlas_name}"
    atlas_dir.mkdir(parents=True, exist_ok=True)

    # Build filename: sub_ses_atlas_software_[source entities]_diffmap
    parts = [subject, session, f"atlas-{atlas_name}"]
    if _software:
        parts.append(f"software-{_software}")
    if _source_entities:
        for key, val in _source_entities.items():
            if key not in ("sub", "ses"):
                parts.append(f"{key}-{val}")
    parts.append("diffmap")
    stem = "_".join(parts)

    out_path = atlas_dir / f"{stem}.tsv"
    df.to_csv(out_path, sep="\t", index=False, float_format="%.6f")
    logger.info("Wrote diffmap TSV (%d rows): %s", len(df), out_path)

    # --- JSON sidecar ---
    if provenance is not None:
        sidecar = provenance.to_dict()
    else:
        # Minimal sidecar when no provenance object was supplied
        sidecar = {
            "subject": subject,
            "session": session,
            "atlas_name": atlas_name,
            "atlas_dseg": None,
            "lut_file": None,
            "scalar_name": None,
            "source_file": None,
            "source_entities": _source_entities or {},
            "software": _software or None,
            "processing": {
                "zero_is_missing": None,
                "stat_tier": None,
                "statistics": list(df.columns),
            },
            "generated_by": {
                "name": "QSIParc",
                "version": qsiparc.__version__,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    json_path = atlas_dir / f"{stem}.json"
    with open(json_path, "w") as f:
        json.dump(sidecar, f, indent=2)
    logger.info("Wrote diffmap sidecar: %s", json_path)

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
                "Description": (
                    "Parcellated diffusion scalar extraction and connectivity"
                    " repackaging from QSIRecon outputs."
                ),
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
