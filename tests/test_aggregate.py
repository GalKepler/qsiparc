"""Tests for the qsiparc aggregate module and CLI command."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from click.testing import CliRunner

from qsiparc.aggregate import (
    aggregate_connectomes,
    aggregate_diffmaps,
    discover_connmatrix_csvs,
    discover_diffmap_tsvs,
    write_aggregate_tsv,
)
from qsiparc.cli import main

# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


class TestDiscoverDiffmapTsvs:
    def test_finds_all_diffmap_tsvs(self, qsiparc_output_tree):
        root = qsiparc_output_tree["root"]
        files = discover_diffmap_tsvs(root)
        # 2 subjects X 2 scalars (FA, MD) = 4 files
        assert len(files) == 4

    def test_atlas_filter(self, qsiparc_output_tree):
        root = qsiparc_output_tree["root"]
        files = discover_diffmap_tsvs(root, atlas=["TestAtlas5"])
        assert len(files) == 4

        files_none = discover_diffmap_tsvs(root, atlas=["NonExistent"])
        assert len(files_none) == 0

    def test_entities_parsed(self, qsiparc_output_tree):
        root = qsiparc_output_tree["root"]
        files = discover_diffmap_tsvs(root)
        subjects = {f.entities["sub"] for f in files}
        assert subjects == {"001", "002"}

    def test_returns_bids_files(self, qsiparc_output_tree):
        root = qsiparc_output_tree["root"]
        files = discover_diffmap_tsvs(root)
        for f in files:
            assert f.path.exists()
            assert f.path.suffix == ".tsv"


class TestDiscoverConnmatrixCsvs:
    def test_finds_all_connmatrix_csvs(self, qsiparc_output_tree):
        root = qsiparc_output_tree["root"]
        files = discover_connmatrix_csvs(root)
        # 2 subjects X 2 measures = 4 files
        assert len(files) == 4

    def test_atlas_filter(self, qsiparc_output_tree):
        root = qsiparc_output_tree["root"]
        files = discover_connmatrix_csvs(root, atlas=["TestAtlas5"])
        assert len(files) == 4

        files_none = discover_connmatrix_csvs(root, atlas=["NonExistent"])
        assert len(files_none) == 0

    def test_entities_parsed(self, qsiparc_output_tree):
        root = qsiparc_output_tree["root"]
        files = discover_connmatrix_csvs(root)
        subjects = {f.entities["sub"] for f in files}
        assert subjects == {"001", "002"}


# ---------------------------------------------------------------------------
# Diffmap aggregation
# ---------------------------------------------------------------------------


class TestAggregateDiffmaps:
    def test_keyed_by_entity_fingerprint(self, qsiparc_output_tree):
        root = qsiparc_output_tree["root"]
        files = discover_diffmap_tsvs(root)
        result = aggregate_diffmaps(files)
        # One key per scalar: FA and MD produce separate entries
        assert len(result) == 2
        fa_key = next(k for k in result if "FA" in k)
        assert "atlas-TestAtlas5" in fa_key
        assert "diffmap" in fa_key

    def test_row_count_per_key(self, qsiparc_output_tree):
        root = qsiparc_output_tree["root"]
        n_regions = qsiparc_output_tree["n_regions"]
        files = discover_diffmap_tsvs(root)
        result = aggregate_diffmaps(files)
        # Each key = one scalar X 2 subjects X n_regions rows
        for df in result.values():
            assert len(df) == 2 * n_regions

    def test_subject_session_columns_present(self, qsiparc_output_tree):
        root = qsiparc_output_tree["root"]
        files = discover_diffmap_tsvs(root)
        result = aggregate_diffmaps(files)
        for df in result.values():
            assert "subject" in df.columns
            assert "session" in df.columns

    def test_subject_values(self, qsiparc_output_tree):
        root = qsiparc_output_tree["root"]
        files = discover_diffmap_tsvs(root)
        result = aggregate_diffmaps(files)
        for df in result.values():
            assert set(df["subject"].unique()) == {"sub-001", "sub-002"}

    def test_preserves_scalar_columns(self, qsiparc_output_tree):
        root = qsiparc_output_tree["root"]
        files = discover_diffmap_tsvs(root)
        result = aggregate_diffmaps(files)
        expected_cols = {
            "subject",
            "session",
            "region_index",
            "region_name",
            "hemisphere",
            "scalar",
            "mean",
            "median",
            "std",
            "iqr",
            "skewness",
            "kurtosis",
            "n_voxels",
            "coverage",
        }
        for df in result.values():
            assert expected_cols.issubset(set(df.columns))

    def test_scalars_split_into_separate_keys(self, qsiparc_output_tree):
        root = qsiparc_output_tree["root"]
        files = discover_diffmap_tsvs(root)
        result = aggregate_diffmaps(files)
        scalars_per_key = {
            k: df["scalar"].unique().tolist() for k, df in result.items()
        }
        # Each key should contain exactly one scalar value (no mixing)
        for k, scalars in scalars_per_key.items():
            assert len(scalars) == 1, f"Key {k!r} has multiple scalars: {scalars}"
        all_scalars = {s for scalars in scalars_per_key.values() for s in scalars}
        assert all_scalars == {"FA", "MD"}

    def test_skips_unreadable_file(self, tmp_path):
        """A corrupted TSV should be skipped with a warning, not crash."""
        from qsiparc.discover import BIDSFile, parse_entities

        bad_path = tmp_path / "sub-001_ses-01_atlas-TestAtlas5_param-FA_diffmap.tsv"
        bad_path.write_text("not\ta\tvalid\ttsv\n\x00\x00\x00")
        files = [BIDSFile(path=bad_path, entities=parse_entities(bad_path.name))]
        # Should not raise
        result = aggregate_diffmaps(files)
        # Either skipped (empty dict) or read successfully — just no exception
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Connectome aggregation
# ---------------------------------------------------------------------------


class TestAggregateConnectomes:
    def test_keyed_by_entity_fingerprint(self, qsiparc_output_tree):
        root = qsiparc_output_tree["root"]
        files = discover_connmatrix_csvs(root)
        result = aggregate_connectomes(files)
        # Two measures → two separate keys
        assert len(result) == 2
        for key in result:
            assert "atlas-TestAtlas5" in key
            assert "connmatrix" in key

    def test_upper_triangle_only(self, qsiparc_output_tree):
        root = qsiparc_output_tree["root"]
        n_regions = qsiparc_output_tree["n_regions"]
        files = discover_connmatrix_csvs(root)
        result = aggregate_connectomes(files, include_diagonal=False)
        n_upper = n_regions * (n_regions - 1) // 2
        # Each key = one measure X 2 subjects X n_upper edges
        for df in result.values():
            assert len(df) == 2 * n_upper
            # Verify i < j for every row (upper triangle, no diagonal)
            assert (df["region_i_index"] < df["region_j_index"]).all()

    def test_with_diagonal(self, qsiparc_output_tree):
        root = qsiparc_output_tree["root"]
        n_regions = qsiparc_output_tree["n_regions"]
        files = discover_connmatrix_csvs(root)
        result = aggregate_connectomes(files, include_diagonal=True)
        n_upper_with_diag = n_regions * (n_regions + 1) // 2
        for df in result.values():
            assert len(df) == 2 * n_upper_with_diag

    def test_region_name_columns(self, qsiparc_output_tree):
        root = qsiparc_output_tree["root"]
        files = discover_connmatrix_csvs(root)
        result = aggregate_connectomes(files)
        labels = qsiparc_output_tree["region_labels"]
        for df in result.values():
            assert "region_i_name" in df.columns
            assert "region_j_name" in df.columns
            assert set(df["region_i_name"].unique()).issubset(set(labels))

    def test_measures_split_into_separate_keys(self, qsiparc_output_tree):
        root = qsiparc_output_tree["root"]
        files = discover_connmatrix_csvs(root)
        result = aggregate_connectomes(files)
        # Each output file corresponds to one measure (it's in the key/filename)
        assert len(result) == 2
        keys = set(result.keys())
        assert any("radius2count" in k for k in keys)
        assert any("radius2meanlength" in k for k in keys)

    def test_skips_missing_sidecar(self, tmp_path):
        """CSV without a JSON sidecar should be skipped with a warning."""
        from qsiparc.discover import BIDSFile, parse_entities

        csv_path = tmp_path / "sub-001_ses-01_atlas-TestAtlas5_desc-test_connmatrix.csv"
        np.savetxt(csv_path, np.eye(3), delimiter=",")
        # No JSON sidecar created
        files = [BIDSFile(path=csv_path, entities=parse_entities(csv_path.name))]
        result = aggregate_connectomes(files)
        # File is skipped → atlas not in result
        assert result == {}


# ---------------------------------------------------------------------------
# write_aggregate_tsv
# ---------------------------------------------------------------------------


class TestWriteAggregateTsv:
    def test_creates_file(self, tmp_path):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        out = tmp_path / "group" / "test.tsv"
        write_aggregate_tsv(df, out)
        assert out.exists()

    def test_tab_separated(self, tmp_path):
        df = pd.DataFrame({"x": [1], "y": [2]})
        out = tmp_path / "out.tsv"
        write_aggregate_tsv(df, out)
        content = out.read_text()
        assert "\t" in content

    def test_creates_parent_dirs(self, tmp_path):
        df = pd.DataFrame({"col": [1]})
        deep_path = tmp_path / "a" / "b" / "c" / "out.tsv"
        write_aggregate_tsv(df, deep_path)
        assert deep_path.exists()

    def test_roundtrip(self, tmp_path):
        df = pd.DataFrame({"subject": ["sub-001"], "mean": [0.5]})
        out = tmp_path / "test.tsv"
        write_aggregate_tsv(df, out)
        loaded = pd.read_csv(out, sep="\t")
        pd.testing.assert_frame_equal(df, loaded)


# ---------------------------------------------------------------------------
# CLI — group structure
# ---------------------------------------------------------------------------


class TestCliGroup:
    def test_main_help_shows_subcommands(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "run" in result.output
        assert "aggregate" in result.output

    def test_run_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--help"])
        assert result.exit_code == 0
        assert "QSIRECON_DIR" in result.output
        assert "OUTPUT_DIR" in result.output

    def test_aggregate_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["aggregate", "--help"])
        assert result.exit_code == 0
        assert "QSIPARC_DIR" in result.output
        assert "--atlas" in result.output
        assert "--data-type" in result.output


# ---------------------------------------------------------------------------
# CLI — aggregate command integration
# ---------------------------------------------------------------------------


def _atlas_subdir(root: Path, data_type: str = "diffmap") -> Path:
    """Return the atlas-TestAtlas5 output subdirectory."""
    return root / "group" / "atlas-TestAtlas5"


class TestAggregateCommand:
    def test_aggregate_all(self, qsiparc_output_tree):
        runner = CliRunner()
        root = qsiparc_output_tree["root"]
        result = runner.invoke(main, ["aggregate", str(root)])
        assert result.exit_code == 0

        atlas_dir = _atlas_subdir(root)
        diffmap_files = list(atlas_dir.glob("*_diffmap.tsv"))
        connmatrix_files = list(atlas_dir.glob("*_connmatrix.tsv"))
        # 2 scalars → 2 diffmap files; 2 measures → 2 connmatrix files
        assert len(diffmap_files) == 2
        assert len(connmatrix_files) == 2

    def test_aggregate_diffmap_only(self, qsiparc_output_tree):
        runner = CliRunner()
        root = qsiparc_output_tree["root"]
        result = runner.invoke(main, ["aggregate", str(root), "--data-type", "diffmap"])
        assert result.exit_code == 0

        atlas_dir = _atlas_subdir(root)
        assert len(list(atlas_dir.glob("*_diffmap.tsv"))) == 2
        assert len(list(atlas_dir.glob("*_connmatrix.tsv"))) == 0

    def test_aggregate_connmatrix_only(self, qsiparc_output_tree):
        runner = CliRunner()
        root = qsiparc_output_tree["root"]
        result = runner.invoke(
            main, ["aggregate", str(root), "--data-type", "connmatrix"]
        )
        assert result.exit_code == 0

        atlas_dir = _atlas_subdir(root)
        assert len(list(atlas_dir.glob("*_diffmap.tsv"))) == 0
        assert len(list(atlas_dir.glob("*_connmatrix.tsv"))) == 2

    def test_custom_output_dir(self, qsiparc_output_tree, tmp_path):
        runner = CliRunner()
        root = qsiparc_output_tree["root"]
        out = tmp_path / "mygroup"
        result = runner.invoke(main, ["aggregate", str(root), "--output-dir", str(out)])
        assert result.exit_code == 0
        atlas_dir = out / "atlas-TestAtlas5"
        assert len(list(atlas_dir.glob("*_diffmap.tsv"))) == 2

    def test_output_filename_contains_entities(self, qsiparc_output_tree):
        runner = CliRunner()
        root = qsiparc_output_tree["root"]
        runner.invoke(main, ["aggregate", str(root), "--data-type", "diffmap"])
        atlas_dir = _atlas_subdir(root)
        names = {f.name for f in atlas_dir.glob("*_diffmap.tsv")}
        # Each filename should include atlas and scalar entities
        assert any("FA" in n for n in names)
        assert any("MD" in n for n in names)
        assert all(n.startswith("atlas-TestAtlas5") for n in names)

    def test_atlas_filter(self, qsiparc_output_tree):
        runner = CliRunner()
        root = str(qsiparc_output_tree["root"])
        result = runner.invoke(main, ["aggregate", root, "--atlas", "TestAtlas5"])
        assert result.exit_code == 0

    def test_atlas_filter_no_match_exits_2(self, qsiparc_output_tree):
        runner = CliRunner()
        root = str(qsiparc_output_tree["root"])
        result = runner.invoke(main, ["aggregate", root, "--atlas", "NonExistentAtlas"])
        assert result.exit_code == 2

    def test_skip_existing_without_force(self, qsiparc_output_tree):
        runner = CliRunner()
        root = qsiparc_output_tree["root"]
        # First run
        runner.invoke(main, ["aggregate", str(root), "--data-type", "diffmap"])
        atlas_dir = _atlas_subdir(root)
        out = next(atlas_dir.glob("*FA*_diffmap.tsv"))
        mtime_after_first = out.stat().st_mtime
        # Second run without --force: 0 new files written
        result = runner.invoke(main, ["aggregate", str(root), "--data-type", "diffmap"])
        assert result.exit_code == 0
        assert "0 file(s) written" in result.output
        assert out.stat().st_mtime == mtime_after_first

    def test_force_overwrites(self, qsiparc_output_tree):
        runner = CliRunner()
        root = qsiparc_output_tree["root"]
        runner.invoke(main, ["aggregate", str(root), "--data-type", "diffmap"])
        result = runner.invoke(
            main, ["aggregate", str(root), "--data-type", "diffmap", "--force"]
        )
        assert result.exit_code == 0
        assert "2 file(s) written" in result.output

    def test_output_content_diffmap(self, qsiparc_output_tree):
        runner = CliRunner()
        root = qsiparc_output_tree["root"]
        runner.invoke(main, ["aggregate", str(root), "--data-type", "diffmap"])
        atlas_dir = _atlas_subdir(root)
        for tsv in atlas_dir.glob("*_diffmap.tsv"):
            df = pd.read_csv(tsv, sep="\t")
            assert "subject" in df.columns
            assert "session" in df.columns
            assert set(df["subject"].unique()) == {"sub-001", "sub-002"}
            # Each file should contain only one scalar
            assert len(df["scalar"].unique()) == 1

    def test_output_content_connmatrix(self, qsiparc_output_tree):
        runner = CliRunner()
        root = qsiparc_output_tree["root"]
        runner.invoke(main, ["aggregate", str(root), "--data-type", "connmatrix"])
        atlas_dir = _atlas_subdir(root)
        for tsv in atlas_dir.glob("*_connmatrix.tsv"):
            df = pd.read_csv(tsv, sep="\t")
            assert "subject" in df.columns
            assert set(df["subject"].unique()) == {"sub-001", "sub-002"}
