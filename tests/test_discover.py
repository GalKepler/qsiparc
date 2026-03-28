"""Tests for qsiparc.discover and qsiparc.atlas."""

from __future__ import annotations

import pytest

from qsiparc.atlas import AtlasLUT, infer_hemisphere, infer_structure, load_lut_from_tsv
from qsiparc.discover import (
    AtlasDsegFile,
    discover_dseg_files,
    discover_scalar_maps,
    discover_sift_weights,
    discover_tractography,
    find_atlas_lut,
    load_lut_for_dseg,
    parse_entities,
)


class TestParseEntities:
    def test_standard_bids(self):
        entities = parse_entities("sub-001_ses-01_space-T1w_seg-Schaefer100_dseg.nii.gz")
        assert entities["sub"] == "001"
        assert entities["ses"] == "01"
        assert entities["space"] == "T1w"
        assert entities["seg"] == "Schaefer100"

    def test_no_entities(self):
        assert parse_entities("README.md") == {}


class TestInferHemisphere:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("LH_Vis_1", "L"),
            ("7Networks_LH_Default_3", "L"),
            ("RH_SomMot_2", "R"),
            ("lh.superiorfrontal", "L"),
            ("rh-inferiorparietal", "R"),
            ("Thalamus", "bilateral"),
            ("Brainstem", "bilateral"),
        ],
    )
    def test_cases(self, name, expected):
        assert infer_hemisphere(name) == expected


class TestInferStructure:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Thalamus_L", "subcortex"),
            ("Caudate_R", "subcortex"),
            ("Cerebellum_Crus_I_L", "cerebellum"),
            ("Brainstem", "brainstem"),
            ("7Networks_LH_Vis_1", "cortex"),
        ],
    )
    def test_cases(self, name, expected):
        assert infer_structure(name) == expected


class TestLoadLutFromTsv:
    def test_load_with_label_column(self, bids_tree):
        """Real QSIRecon TSVs have 'index' and 'label' columns."""
        lut = load_lut_from_tsv(bids_tree["lut"], atlas_name="TestAtlas5")
        assert len(lut) == 5
        assert lut[1].name == "LH_Vis_1"
        assert lut[4].structure == "subcortex"  # inferred from "Thalamus_L"

    def test_load_with_name_column(self, tmp_path):
        """TSVs with explicit 'name', 'hemisphere', 'structure' columns also work."""
        tsv = tmp_path / "lut.tsv"
        tsv.write_text(
            "index\tname\themisphere\tstructure\n"
            "1\tLH_Vis_1\tL\tcortex\n"
            "4\tThalamus_L\tL\tsubcortex\n"
        )
        lut = load_lut_from_tsv(tsv, atlas_name="X")
        assert lut[1].hemisphere == "L"
        assert lut[4].structure == "subcortex"

    def test_to_dataframe(self, bids_tree):
        lut = load_lut_from_tsv(bids_tree["lut"], atlas_name="TestAtlas5")
        df = lut.to_dataframe()
        assert list(df.columns) == ["region_index", "region_name", "hemisphere", "structure"]
        assert len(df) == 5


class TestFindAtlasLut:
    def test_found(self, bids_tree):
        lut_path = find_atlas_lut(bids_tree["root"], "TestAtlas5")
        assert lut_path is not None
        assert lut_path.exists()
        assert lut_path.name == "atlas-TestAtlas5_dseg.tsv"

    def test_not_found_wrong_name(self, bids_tree):
        assert find_atlas_lut(bids_tree["root"], "NonExistent") is None

    def test_not_found_no_atlases_dir(self, tmp_path):
        assert find_atlas_lut(tmp_path / "empty", "AAL116") is None


class TestLoadLutForDseg:
    def test_uses_lut_path(self, bids_tree):
        dseg_file = discover_dseg_files(bids_tree["root"])[0]
        assert dseg_file.lut_path is not None
        lut = load_lut_for_dseg(dseg_file)
        assert len(lut) == 5
        assert lut.atlas_name == "TestAtlas5"

    def test_fallback_when_no_lut(self, bids_tree):
        from qsiparc.discover import AtlasDsegFile
        dseg_file = AtlasDsegFile(
            path=bids_tree["dseg"],
            entities={"sub": "001", "ses": "01"},
            atlas_name="FakeAtlas",
            lut_path=None,
        )
        lut = load_lut_for_dseg(dseg_file)
        # Fallback creates generic region names from NIfTI labels
        assert len(lut) == 5
        assert lut[1].name.startswith("region_")


class TestDiscoverDsegFiles:
    def test_find_all(self, bids_tree):
        files = discover_dseg_files(bids_tree["root"])
        assert len(files) == 1
        dseg = files[0]
        assert isinstance(dseg, AtlasDsegFile)
        assert dseg.atlas_name == "TestAtlas5"
        assert dseg.lut_path is not None
        assert dseg.lut_path.exists()

    def test_filter_atlas(self, bids_tree):
        files = discover_dseg_files(bids_tree["root"], atlas="NonExistent")
        assert len(files) == 0

    def test_filter_atlas_match(self, bids_tree):
        files = discover_dseg_files(bids_tree["root"], atlas="TestAtlas5")
        assert len(files) == 1

    def test_filter_subject(self, bids_tree):
        files = discover_dseg_files(bids_tree["root"], participant_label="sub-001")
        assert len(files) == 1
        files = discover_dseg_files(bids_tree["root"], participant_label="sub-999")
        assert len(files) == 0

    def test_subject_without_prefix(self, bids_tree):
        files = discover_dseg_files(bids_tree["root"], participant_label="001")
        assert len(files) == 1


class TestDiscoverScalarMaps:
    def test_find_all(self, bids_tree):
        files = discover_scalar_maps(bids_tree["root"], "sub-001", "ses-01")
        assert len(files) == 2
        names = {f.path.name for f in files}
        assert any("FA" in n for n in names)
        assert any("MD" in n for n in names)

    def test_filter_scalars(self, bids_tree):
        files = discover_scalar_maps(bids_tree["root"], "sub-001", "ses-01", scalars=["FA"])
        assert len(files) == 1
        assert "FA" in files[0].path.name

    def test_entities_parsed(self, bids_tree):
        files = discover_scalar_maps(bids_tree["root"], "sub-001", "ses-01", scalars=["FA"])
        assert files[0].entities.get("param") == "FA"
        assert files[0].entities.get("model") == "DTI"

    def test_no_derivatives_returns_empty(self, tmp_path):
        root = tmp_path / "empty_root"
        root.mkdir()
        files = discover_scalar_maps(root, "sub-001", "ses-01")
        assert files == []


class TestDiscoverTractography:
    def test_find_tck(self, bids_tree):
        files = discover_tractography(bids_tree["root"], "sub-001", "ses-01")
        assert len(files) == 1
        assert files[0].path.name.endswith("_streamlines.tck.gz")
        assert files[0].entities.get("model") == "ifod2"

    def test_no_derivatives_returns_empty(self, tmp_path):
        root = tmp_path / "empty"
        root.mkdir()
        assert discover_tractography(root, "sub-001", "ses-01") == []


class TestDiscoverSiftWeights:
    def test_find_weights(self, bids_tree):
        files = discover_sift_weights(bids_tree["root"], "sub-001", "ses-01")
        assert len(files) == 1
        assert files[0].path.name.endswith("_streamlineweights.csv")
        assert files[0].entities.get("model") == "sift2"

    def test_no_derivatives_returns_empty(self, tmp_path):
        root = tmp_path / "empty"
        root.mkdir()
        assert discover_sift_weights(root, "sub-001", "ses-01") == []
