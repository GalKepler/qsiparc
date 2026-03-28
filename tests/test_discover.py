"""Tests for qsiparc.discover and qsiparc.atlas."""

from __future__ import annotations

import pytest

from qsiparc.atlas import AtlasLUT, infer_hemisphere, infer_structure, load_lut_from_tsv
from qsiparc.discover import discover_dseg_files, discover_scalar_maps, parse_entities


class TestParseEntities:
    def test_standard_bids(self):
        entities = parse_entities("sub-001_ses-01_space-T1w_atlas-Schaefer100_dseg.nii.gz")
        assert entities["sub"] == "001"
        assert entities["ses"] == "01"
        assert entities["space"] == "T1w"
        assert entities["atlas"] == "Schaefer100"

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
    def test_load(self, bids_tree):
        lut = load_lut_from_tsv(bids_tree["lut"], atlas_name="TestAtlas5")
        assert len(lut) == 5
        assert lut[1].name == "LH_Vis_1"
        assert lut[4].structure == "subcortex"

    def test_to_dataframe(self, bids_tree):
        lut = load_lut_from_tsv(bids_tree["lut"], atlas_name="TestAtlas5")
        df = lut.to_dataframe()
        assert list(df.columns) == ["region_index", "region_name", "hemisphere", "structure"]
        assert len(df) == 5


class TestDiscoverDsegFiles:
    def test_find_all(self, bids_tree):
        files = discover_dseg_files(bids_tree["root"])
        assert len(files) == 1
        assert files[0].atlas == "TestAtlas5"

    def test_filter_atlas(self, bids_tree):
        files = discover_dseg_files(bids_tree["root"], atlas="NonExistent")
        assert len(files) == 0

    def test_filter_subject(self, bids_tree):
        files = discover_dseg_files(bids_tree["root"], participant_label="sub-001")
        assert len(files) == 1
        files = discover_dseg_files(bids_tree["root"], participant_label="sub-999")
        assert len(files) == 0


class TestDiscoverScalarMaps:
    def test_find_all(self, bids_tree):
        files = discover_scalar_maps(bids_tree["root"], "sub-001", "ses-01")
        # Should find FA and MD but not dseg
        assert len(files) == 2
        names = {f.path.name for f in files}
        assert any("FA" in n for n in names)
        assert any("MD" in n for n in names)

    def test_filter_scalars(self, bids_tree):
        files = discover_scalar_maps(bids_tree["root"], "sub-001", "ses-01", scalars=["FA"])
        assert len(files) == 1
        assert "FA" in files[0].path.name
