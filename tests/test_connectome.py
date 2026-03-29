"""Tests for the connectome construction module.

Unit tests verify tck2connectome command assembly without calling MRtrix3.
Integration tests are skipped when MRtrix3 is not on PATH.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from qsiparc.connectome import (
    MEASURES,
    _ensure_plain_tck,
    build_tck2connectome_cmd,
    check_mrtrix3,
    find_sift_weights_for_tck,
)
from qsiparc.discover import AtlasDsegFile, BIDSFile

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bids_file(path: Path) -> BIDSFile:
    from qsiparc.discover import parse_entities

    return BIDSFile(path=path, entities=parse_entities(path.name))


def _make_dseg_file(path: Path, atlas_name: str = "TestAtlas5") -> AtlasDsegFile:
    from qsiparc.discover import parse_entities

    return AtlasDsegFile(
        path=path,
        entities=parse_entities(path.name),
        atlas_name=atlas_name,
        lut_path=None,
    )


# ---------------------------------------------------------------------------
# _ensure_plain_tck
# ---------------------------------------------------------------------------


def test_ensure_plain_tck_passthrough(tmp_path: Path):
    """Plain .tck files are yielded unchanged."""
    tck = tmp_path / "tracks.tck"
    tck.write_bytes(b"fake tck content")
    with _ensure_plain_tck(tck) as plain:
        assert plain == tck
        assert plain.exists()
    # Original file must still exist after context exit
    assert tck.exists()


def test_ensure_plain_tck_decompresses_gz(tmp_path: Path):
    """A .tck.gz file is decompressed to a temp .tck."""
    import gzip

    content = b"fake tck binary content"
    tck_gz = tmp_path / "tracks.tck.gz"
    with gzip.open(tck_gz, "wb") as f:
        f.write(content)

    with _ensure_plain_tck(tck_gz) as plain:
        assert plain != tck_gz
        assert plain.suffix == ".tck"
        assert plain.read_bytes() == content

    # Temp file must be cleaned up after context exit
    assert not plain.exists()


def test_ensure_plain_tck_cleans_up_on_exception(tmp_path: Path):
    """Temp .tck is deleted even if an exception is raised inside the block."""
    import gzip

    tck_gz = tmp_path / "tracks.tck.gz"
    with gzip.open(tck_gz, "wb") as f:
        f.write(b"data")

    tmp_path_ref = None
    with pytest.raises(RuntimeError), _ensure_plain_tck(tck_gz) as plain:
        tmp_path_ref = plain
        raise RuntimeError("simulated failure")

    assert tmp_path_ref is not None
    assert not tmp_path_ref.exists()


# ---------------------------------------------------------------------------
# check_mrtrix3
# ---------------------------------------------------------------------------


def test_check_mrtrix3_found():
    with patch("shutil.which", return_value="/usr/bin/tck2connectome"):
        assert check_mrtrix3() is True


def test_check_mrtrix3_missing():
    with patch("shutil.which", return_value=None):
        assert check_mrtrix3() is False


# ---------------------------------------------------------------------------
# find_sift_weights_for_tck
# ---------------------------------------------------------------------------


def test_find_sift_weights_streamlineweights(tmp_path: Path):
    tck = tmp_path / "sub-001_ses-01_streamlines.tck.gz"
    tck.touch()
    weights = tmp_path / "sub-001_ses-01_streamlineweights.csv"
    weights.touch()

    result = find_sift_weights_for_tck(tck)
    assert result == weights


def test_find_sift_weights_siftweights(tmp_path: Path):
    tck = tmp_path / "sub-001_ses-01_streamlines.tck.gz"
    tck.touch()
    weights = tmp_path / "sub-001_ses-01_siftweights.csv"
    weights.touch()

    result = find_sift_weights_for_tck(tck)
    assert result == weights


def test_find_sift_weights_none(tmp_path: Path):
    tck = tmp_path / "sub-001_ses-01_streamlines.tck.gz"
    tck.touch()

    result = find_sift_weights_for_tck(tck)
    assert result is None


def test_find_sift_weights_prefers_streamlineweights(tmp_path: Path):
    """streamlineweights.csv takes priority over siftweights.csv."""
    tck = tmp_path / "sub-001_ses-01_streamlines.tck.gz"
    tck.touch()
    sw = tmp_path / "sub-001_ses-01_streamlineweights.csv"
    sw.touch()
    sf = tmp_path / "sub-001_ses-01_siftweights.csv"
    sf.touch()

    result = find_sift_weights_for_tck(tck)
    assert result == sw


# ---------------------------------------------------------------------------
# build_tck2connectome_cmd — exact flag verification
# ---------------------------------------------------------------------------

TCK = Path("/data/sub-001_ses-01_streamlines.tck.gz")
DSEG = Path("/data/sub-001_ses-01_seg-TestAtlas5_dseg.nii.gz")
WEIGHTS = Path("/data/sub-001_ses-01_streamlineweights.csv")


def test_cmd_sift_invnodevol_radius2_count():
    out = Path("/out/connmatrix.csv")
    cmd = build_tck2connectome_cmd(
        TCK,
        DSEG,
        out,
        "sift_invnodevol_radius2_count",
        sift_weights=WEIGHTS,
    )
    assert cmd[0] == "tck2connectome"
    assert str(TCK) in cmd
    assert str(DSEG) in cmd
    assert str(out) in cmd
    assert "-assignment_radial_search" in cmd
    assert cmd[cmd.index("-assignment_radial_search") + 1] == "2"
    assert "-scale_invnodevol" in cmd
    assert "-symmetric" in cmd
    assert "-stat_edge" in cmd
    assert cmd[cmd.index("-stat_edge") + 1] == "sum"
    assert "-tck_weights_in" in cmd
    assert cmd[cmd.index("-tck_weights_in") + 1] == str(WEIGHTS)


def test_cmd_radius2_meanlength():
    out = Path("/out/connmatrix.csv")
    cmd = build_tck2connectome_cmd(TCK, DSEG, out, "radius2_meanlength")
    assert "-scale_length" in cmd
    assert "-stat_edge" in cmd
    assert cmd[cmd.index("-stat_edge") + 1] == "mean"
    assert "-tck_weights_in" not in cmd
    assert "-scale_invnodevol" not in cmd


def test_cmd_radius2_count():
    out = Path("/out/connmatrix.csv")
    cmd = build_tck2connectome_cmd(TCK, DSEG, out, "radius2_count")
    assert "-stat_edge" in cmd
    assert cmd[cmd.index("-stat_edge") + 1] == "sum"
    assert "-tck_weights_in" not in cmd
    assert "-scale_invnodevol" not in cmd
    assert "-scale_length" not in cmd


def test_cmd_sift_radius2_count():
    out = Path("/out/connmatrix.csv")
    cmd = build_tck2connectome_cmd(
        TCK, DSEG, out, "sift_radius2_count", sift_weights=WEIGHTS
    )
    assert "-tck_weights_in" in cmd
    assert cmd[cmd.index("-tck_weights_in") + 1] == str(WEIGHTS)
    assert "-scale_invnodevol" not in cmd
    assert "-scale_length" not in cmd
    assert "-stat_edge" in cmd
    assert cmd[cmd.index("-stat_edge") + 1] == "sum"


def test_cmd_unknown_measure_raises():
    with pytest.raises(ValueError, match="Unknown measure"):
        build_tck2connectome_cmd(TCK, DSEG, Path("/out/x.csv"), "not_a_real_measure")


def test_cmd_missing_sift_weights_raises():
    """Measures needing SIFT2 weights must raise if weights are None."""
    for measure in ("sift_invnodevol_radius2_count", "sift_radius2_count"):
        with pytest.raises(ValueError, match="SIFT2 weights"):
            build_tck2connectome_cmd(TCK, DSEG, Path("/out/x.csv"), measure)


def test_cmd_search_radius_is_2_for_all_measures():
    """All four measures must use -assignment_radial_search 2."""
    out = Path("/out/connmatrix.csv")
    for measure in MEASURES:
        needs_sw = MEASURES[measure]["needs_sift_weights"]
        sw = WEIGHTS if needs_sw else None
        cmd = build_tck2connectome_cmd(TCK, DSEG, out, measure, sift_weights=sw)
        assert "-assignment_radial_search" in cmd
        idx = cmd.index("-assignment_radial_search")
        assert cmd[idx + 1] == "2", f"measure {measure}: expected radius 2"


def test_cmd_symmetric_for_all_measures():
    """All four measures must include -symmetric."""
    out = Path("/out/connmatrix.csv")
    for measure in MEASURES:
        needs_sw = MEASURES[measure]["needs_sift_weights"]
        sw = WEIGHTS if needs_sw else None
        cmd = build_tck2connectome_cmd(TCK, DSEG, out, measure, sift_weights=sw)
        assert "-symmetric" in cmd, f"measure {measure}: -symmetric missing"


# ---------------------------------------------------------------------------
# build_connectomes — mocked subprocess
# ---------------------------------------------------------------------------


def test_build_connectomes_writes_all_measures(
    tmp_path: Path,
    bids_tree: dict,
    five_region_lut,
):
    """With mocked subprocess, build_connectomes writes 4 CSV+JSON pairs."""
    import json

    import numpy as np

    tck_file = _make_bids_file(bids_tree["tck"])
    dseg_file = _make_dseg_file(bids_tree["dseg"])
    output_dir = tmp_path / "out"

    # Patch subprocess.run to write a fake 5x5 matrix CSV
    def fake_run(cmd, **kwargs):
        # The third positional arg in the cmd is the output CSV path
        out_csv = Path(cmd[3])
        np.savetxt(out_csv, np.eye(5), delimiter=",", fmt="%.1f")
        mock = MagicMock()
        mock.returncode = 0
        return mock

    with patch("qsiparc.connectome.subprocess.run", side_effect=fake_run):
        from qsiparc.connectome import build_connectomes

        results = build_connectomes(
            tck_file=tck_file,
            dseg_file=dseg_file,
            lut=five_region_lut,
            output_dir=output_dir,
            subject="sub-001",
            session="ses-01",
        )

    assert len(results) == 4

    measure_names = {r.measure for r in results}
    assert measure_names == set(MEASURES.keys())

    for result in results:
        assert result.csv_path.exists()
        assert result.json_path.exists()
        sidecar = json.loads(result.json_path.read_text())
        assert sidecar["atlas_name"] == "TestAtlas5"
        assert sidecar["measure"] == result.measure
        assert sidecar["n_regions"] == 5
        assert sidecar["symmetric"] is True
        assert "region_labels" in sidecar
        assert "tck2connectome_cmd" in sidecar
        # The command must NOT reference the .tck.gz — only plain .tck
        assert not result.cmd[1].endswith(".gz")


def test_build_connectomes_skips_sift_measures_without_weights(
    tmp_path: Path,
    five_region_lut,
):
    """Without SIFT2 weights, the two SIFT-dependent measures are skipped."""
    # Create a tck with no adjacent weights file
    tck_dir = tmp_path / "dwi"
    tck_dir.mkdir()
    tck_path = tck_dir / "sub-001_ses-01_streamlines.tck.gz"
    tck_path.touch()
    dseg_path = tmp_path / "sub-001_ses-01_seg-TestAtlas5_dseg.nii.gz"
    dseg_path.touch()

    tck_file = _make_bids_file(tck_path)
    dseg_file = _make_dseg_file(dseg_path)

    def fake_run(cmd, **kwargs):
        out_csv = Path(cmd[3])
        np.savetxt(out_csv, np.eye(5), delimiter=",", fmt="%.1f")
        mock = MagicMock()
        mock.returncode = 0
        return mock

    with patch("qsiparc.connectome.subprocess.run", side_effect=fake_run):
        from qsiparc.connectome import build_connectomes

        results = build_connectomes(
            tck_file=tck_file,
            dseg_file=dseg_file,
            lut=five_region_lut,
            output_dir=tmp_path / "out",
            subject="sub-001",
            session="ses-01",
        )

    # Only the two non-SIFT measures should succeed
    measures = {r.measure for r in results}
    assert measures == {"radius2_count", "radius2_meanlength"}


def test_build_connectomes_disambiguates_multiple_tck_files(
    tmp_path: Path,
    five_region_lut,
):
    """Two tck files in the same session write to distinct output filenames."""
    dseg_path = tmp_path / "sub-001_ses-01_seg-TestAtlas5_dseg.nii.gz"
    dseg_path.touch()
    dseg_file = _make_dseg_file(dseg_path)

    tck_dir = tmp_path / "dwi"
    tck_dir.mkdir()
    tck_a = tck_dir / "sub-001_ses-01_model-ifod2_streamlines.tck.gz"
    tck_b = tck_dir / "sub-001_ses-01_model-sdstream_streamlines.tck.gz"
    tck_a.touch()
    tck_b.touch()

    def fake_run(cmd, **kwargs):
        out_csv = Path(cmd[3])
        np.savetxt(out_csv, np.eye(5), delimiter=",", fmt="%.1f")
        mock = MagicMock()
        mock.returncode = 0
        return mock

    with patch("qsiparc.connectome.subprocess.run", side_effect=fake_run):
        from qsiparc.connectome import build_connectomes

        results_a = build_connectomes(
            tck_file=_make_bids_file(tck_a),
            dseg_file=dseg_file,
            lut=five_region_lut,
            output_dir=tmp_path / "out",
            subject="sub-001",
            session="ses-01",
        )
        results_b = build_connectomes(
            tck_file=_make_bids_file(tck_b),
            dseg_file=dseg_file,
            lut=five_region_lut,
            output_dir=tmp_path / "out",
            subject="sub-001",
            session="ses-01",
        )

    paths_a = {r.csv_path for r in results_a}
    paths_b = {r.csv_path for r in results_b}
    # No overlap between the two sets of output files
    assert paths_a.isdisjoint(paths_b)
    # model entity is present in filenames
    assert all("model-ifod2" in str(p) for p in paths_a)
    assert all("model-sdstream" in str(p) for p in paths_b)


def test_build_connectomes_raises_on_nonzero_exit(
    tmp_path: Path,
    five_region_lut,
):
    """Non-zero tck2connectome exit code raises CalledProcessError."""
    import subprocess

    tck_dir = tmp_path / "dwi"
    tck_dir.mkdir()
    tck_path = tck_dir / "sub-001_ses-01_streamlines.tck.gz"
    tck_path.touch()
    dseg_path = tmp_path / "sub-001_ses-01_seg-TestAtlas5_dseg.nii.gz"
    dseg_path.touch()

    tck_file = _make_bids_file(tck_path)
    dseg_file = _make_dseg_file(dseg_path)

    def failing_run(cmd, **kwargs):
        mock = MagicMock()
        mock.returncode = 1
        mock.stderr = "tck2connectome: some error"
        mock.stdout = ""
        return mock

    with patch("qsiparc.connectome.subprocess.run", side_effect=failing_run):
        from qsiparc.connectome import build_connectomes

        with pytest.raises(subprocess.CalledProcessError):
            build_connectomes(
                tck_file=tck_file,
                dseg_file=dseg_file,
                lut=five_region_lut,
                output_dir=tmp_path / "out",
                subject="sub-001",
                session="ses-01",
            )


# ---------------------------------------------------------------------------
# Integration test (skipped without MRtrix3 or real .tck data)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not check_mrtrix3(), reason="MRtrix3 not available")
@pytest.mark.skip(
    reason=(
        "Requires a valid .tck tractogram; "
        "synthetic placeholder files are not supported by tck2connectome"
    )
)
def test_build_connectomes_integration(tmp_path, bids_tree, five_region_lut):
    """Full end-to-end test against real tck2connectome.

    Skipped in CI: requires a real .tck tractogram from QSIRecon output, which
    is too large to ship with the test suite.  Run manually with real data.
    """
    from qsiparc.connectome import build_connectomes

    tck_file = _make_bids_file(bids_tree["tck"])
    dseg_file = _make_dseg_file(bids_tree["dseg"])

    results = build_connectomes(
        tck_file=tck_file,
        dseg_file=dseg_file,
        lut=five_region_lut,
        output_dir=tmp_path / "out",
        subject="sub-001",
        session="ses-01",
    )

    assert len(results) > 0
    for result in results:
        assert result.matrix.ndim == 2
        assert result.matrix.shape[0] == result.matrix.shape[1]
