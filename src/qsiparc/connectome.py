"""Connectome construction: run tck2connectome for four connectivity measures.

QSIRecon produces tractography (.tck) and SIFT2 streamline weights, but does
NOT run tck2connectome — that step is QSIParc's responsibility.

For each tractogram × atlas combination, QSIParc runs four tck2connectome
variants and writes a CSV matrix + JSON sidecar for each.
"""

from __future__ import annotations

import contextlib
import gzip
import json
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from qsiparc.atlas import AtlasLUT
from qsiparc.discover import AtlasDsegFile, BIDSFile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Measure definitions: maps each measure name to its tck2connectome flags
# and whether SIFT2 streamline weights are required.
# ---------------------------------------------------------------------------

MEASURES: dict[str, dict] = {
    "sift_invnodevol_radius2_count": {
        "flags": [
            "-assignment_radial_search", "2",
            "-scale_invnodevol",
            "-symmetric",
            "-stat_edge", "sum",
        ],
        "needs_sift_weights": True,
    },
    "radius2_meanlength": {
        "flags": [
            "-assignment_radial_search", "2",
            "-scale_length",
            "-symmetric",
            "-stat_edge", "mean",
        ],
        "needs_sift_weights": False,
    },
    "radius2_count": {
        "flags": [
            "-assignment_radial_search", "2",
            "-symmetric",
            "-stat_edge", "sum",
        ],
        "needs_sift_weights": False,
    },
    "sift_radius2_count": {
        "flags": [
            "-assignment_radial_search", "2",
            "-symmetric",
            "-stat_edge", "sum",
        ],
        "needs_sift_weights": True,
    },
}


def check_mrtrix3() -> bool:
    """Return True if tck2connectome is reachable on PATH."""
    return shutil.which("tck2connectome") is not None


@contextlib.contextmanager
def _ensure_plain_tck(tck_path: Path):
    """Yield a plain .tck path, decompressing .tck.gz to a temp file if needed.

    MRtrix3's tck2connectome does not accept gzip-compressed tractograms.
    When *tck_path* ends with ``.tck.gz``, this context manager decompresses
    it to a temporary ``.tck`` file, yields that path, then deletes the
    temporary file on exit.  Plain ``.tck`` files are yielded unchanged.
    """
    if tck_path.suffix == ".gz" and tck_path.stem.endswith(".tck"):
        tmp = tempfile.NamedTemporaryFile(suffix=".tck", delete=False)
        tmp_path = Path(tmp.name)
        try:
            logger.debug("Decompressing %s → %s", tck_path.name, tmp_path.name)
            with gzip.open(tck_path, "rb") as src, open(tmp_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            yield tmp_path
        finally:
            tmp_path.unlink(missing_ok=True)
    else:
        yield tck_path


def find_sift_weights_for_tck(tck_path: Path) -> Path | None:
    """Find SIFT2 streamline weight file adjacent to a tractography file.

    Searches the same directory as *tck_path* for files matching:
        ``*_streamlineweights.csv``
        ``*_siftweights.csv``

    Returns the first match, or None if nothing is found.
    """
    parent = tck_path.parent
    for pattern in ("*_streamlineweights.csv", "*_siftweights.csv"):
        candidates = sorted(parent.glob(pattern))
        if candidates:
            return candidates[0]
    return None


def build_tck2connectome_cmd(
    tck_path: Path,
    dseg_path: Path,
    out_csv: Path,
    measure: str,
    sift_weights: Path | None = None,
) -> list[str]:
    """Assemble the tck2connectome command for a given measure.

    Parameters
    ----------
    tck_path : Path
        Input tractogram (.tck or .tck.gz).
    dseg_path : Path
        Atlas parcellation in subject diffusion space (node image).
    out_csv : Path
        Destination CSV for the N×N matrix.
    measure : str
        One of the keys in MEASURES.
    sift_weights : Path, optional
        SIFT2 weight file; required when MEASURES[measure]["needs_sift_weights"]
        is True.

    Returns
    -------
    list[str]
        Full argv list starting with ``"tck2connectome"``.

    Raises
    ------
    ValueError
        If *measure* is unknown or SIFT2 weights are required but not provided.
    """
    if measure not in MEASURES:
        raise ValueError(
            f"Unknown measure: {measure!r}. Valid measures: {list(MEASURES)}"
        )

    spec = MEASURES[measure]
    if spec["needs_sift_weights"] and sift_weights is None:
        raise ValueError(
            f"Measure {measure!r} requires SIFT2 weights but none were provided."
        )

    cmd: list[str] = [
        "tck2connectome",
        str(tck_path),
        str(dseg_path),
        str(out_csv),
    ]
    cmd.extend(spec["flags"])
    if spec["needs_sift_weights"] and sift_weights is not None:
        cmd.extend(["-tck_weights_in", str(sift_weights)])

    return cmd


@dataclass
class ConnectomeResult:
    """A computed connectivity matrix with full provenance metadata."""

    matrix: np.ndarray  # shape (N, N)
    atlas_name: str
    measure: str  # e.g. "sift_invnodevol_radius2_count"
    region_labels: list[str]
    csv_path: Path
    json_path: Path
    tck_path: Path
    dseg_path: Path
    sift_weights_path: Path | None
    cmd: list[str]


def build_connectomes(
    tck_file: BIDSFile,
    dseg_file: AtlasDsegFile,
    lut: AtlasLUT,
    output_dir: Path,
    subject: str,
    session: str,
    force: bool = False,
) -> list[ConnectomeResult]:
    """Run all four tck2connectome measures for one tractogram × atlas pair.

    Skips measures that require SIFT2 weights when none are found adjacent to
    the tractogram. Raises on non-zero tck2connectome exit code (per-measure
    failure — caller decides whether to continue with remaining subjects).

    Parameters
    ----------
    tck_file : BIDSFile
        Discovered tractography file.
    dseg_file : AtlasDsegFile
        Atlas parcellation in subject diffusion space.
    lut : AtlasLUT
        Atlas LUT providing region labels for JSON sidecars.
    output_dir : Path
        Root output directory (BIDS-derivative layout).
    subject : str
        Subject label with prefix (e.g. ``"sub-001"``).
    session : str
        Session label with prefix (e.g. ``"ses-01"``).

    Returns
    -------
    list[ConnectomeResult]
        One entry per successfully completed measure.

    Raises
    ------
    subprocess.CalledProcessError
        If tck2connectome exits with a non-zero code for any measure.
    """
    atlas_dir = (
        output_dir / subject / session / "dwi" / f"atlas-{dseg_file.atlas_name}"
    )
    atlas_dir.mkdir(parents=True, exist_ok=True)

    sift_weights = find_sift_weights_for_tck(tck_file.path)
    region_labels = [r.name for r in lut.regions]
    results: list[ConnectomeResult] = []

    # Build a string of tck-source entities to disambiguate outputs when
    # multiple tractograms exist in the same session (e.g. iFOD2 + SDStream).
    # Skip sub/ses — they're already in the stem prefix.
    _skip = {"sub", "ses"}
    tck_entity_str = "_".join(
        f"{k}-{v}"
        for k, v in tck_file.entities.items()
        if k not in _skip
    )

    with _ensure_plain_tck(tck_file.path) as plain_tck:
        for measure, spec in MEASURES.items():
            if spec["needs_sift_weights"] and sift_weights is None:
                logger.warning(
                    "%s/%s | Skipping measure %s: no SIFT2 weights found near %s",
                    subject,
                    session,
                    measure,
                    tck_file.path.name,
                )
                continue

            stem_parts = [subject, session]
            if tck_entity_str:
                stem_parts.append(tck_entity_str)
            stem_parts += [
                f"atlas-{dseg_file.atlas_name}",
                f"desc-{measure}",
                "connmatrix",
            ]
            stem = "_".join(stem_parts)
            csv_path = atlas_dir / f"{stem}.csv"
            json_path = atlas_dir / f"{stem}.json"

            if csv_path.exists() and not force:
                logger.info(
                    "%s/%s | Skipping existing connectome: %s",
                    subject,
                    session,
                    csv_path.name,
                )
                continue

            sw = sift_weights if spec["needs_sift_weights"] else None
            cmd = build_tck2connectome_cmd(
                plain_tck, dseg_file.path, csv_path, measure, sw
            )

            logger.info("%s/%s | Running: %s", subject, session, " ".join(cmd))
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(
                    "%s/%s | tck2connectome failed for measure %s (exit %d):\n%s",
                    subject,
                    session,
                    measure,
                    result.returncode,
                    result.stderr,
                )
                raise subprocess.CalledProcessError(
                    result.returncode, cmd, result.stdout, result.stderr
                )

            matrix = np.loadtxt(csv_path, delimiter=",")

            sidecar = {
                "atlas_name": dseg_file.atlas_name,
                "measure": measure,
                "n_regions": len(region_labels),
                "region_labels": region_labels,
                "symmetric": True,
                "source_tck": str(tck_file.path),
                "source_dseg": str(dseg_file.path),
                "sift_weights": str(sift_weights) if sift_weights else None,
                "tck2connectome_cmd": cmd,
            }
            with open(json_path, "w") as f:
                json.dump(sidecar, f, indent=2)

            logger.info("%s/%s | Wrote connectome: %s", subject, session, csv_path)
            results.append(
                ConnectomeResult(
                    matrix=matrix,
                    atlas_name=dseg_file.atlas_name,
                    measure=measure,
                    region_labels=region_labels,
                    csv_path=csv_path,
                    json_path=json_path,
                    tck_path=tck_file.path,
                    dseg_path=dseg_file.path,
                    sift_weights_path=sift_weights,
                    cmd=cmd,
                )
            )

    return results
