"""Tests for qsiparc.extract — regional scalar extraction."""

from __future__ import annotations

import numpy as np
import pytest

from qsiparc.extract import extract_scalar_map, merge_extraction_results


class TestExtractScalarMap:
    """Tests for the full extraction pipeline."""

    def test_uniform_scalar(self, five_region_lut, synthetic_dseg, synthetic_scalar_uniform):
        result = extract_scalar_map(
            scalar_path=synthetic_scalar_uniform,
            dseg_path=synthetic_dseg,
            lut=five_region_lut,
            scalar_name="FA",
        )
        df = result.stats_df

        assert len(df) == 5
        assert set(df["scalar"]) == {"FA"}
        # All regions should have mean ≈ 0.5
        assert all(df["mean"].between(0.49, 0.51))
        # Std should be 0 (or NaN for regions with only 1 voxel)
        uniform_std = df.loc[df["voxel_count"] > 1, "std"]
        assert all(uniform_std < 1e-10)

    def test_gradient_scalar(self, five_region_lut, synthetic_dseg, synthetic_scalar_gradient):
        result = extract_scalar_map(
            scalar_path=synthetic_scalar_gradient,
            dseg_path=synthetic_dseg,
            lut=five_region_lut,
            scalar_name="MD",
        )
        df = result.stats_df

        assert len(df) == 5
        # Each region spans all y values, so mean should be mean(0.1..1.0) = 0.55
        for _, row in df.iterrows():
            if row["voxel_count"] > 0:
                assert row["mean"] == pytest.approx(0.55, abs=0.01)

    def test_shape_mismatch_raises(self, five_region_lut, synthetic_dseg):
        import nibabel as nib
        wrong_shape = nib.Nifti1Image(np.zeros((5, 5, 5)), np.eye(4))
        with pytest.raises(ValueError, match="Shape mismatch"):
            extract_scalar_map(wrong_shape, synthetic_dseg, five_region_lut, "FA")


class TestMergeResults:
    """Tests for combining multiple ExtractionResults."""

    def test_merge(self, five_region_lut, synthetic_dseg, synthetic_scalar_uniform, synthetic_scalar_gradient):
        r1 = extract_scalar_map(synthetic_scalar_uniform, synthetic_dseg, five_region_lut, "FA")
        r2 = extract_scalar_map(synthetic_scalar_gradient, synthetic_dseg, five_region_lut, "MD")

        combined = merge_extraction_results([r1, r2])
        assert len(combined) == 10  # 5 regions × 2 scalars
        assert set(combined["scalar"]) == {"FA", "MD"}

    def test_merge_empty(self):
        combined = merge_extraction_results([])
        assert len(combined) == 0
