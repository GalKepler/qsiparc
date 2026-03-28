"""Shared test fixtures: synthetic NIfTI data and BIDS directory trees.

These fixtures produce small (10×10×10) volumes with known values so that
extraction results can be verified deterministically.
"""

from __future__ import annotations

import json
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from qsiparc.atlas import AtlasLUT, RegionInfo


@pytest.fixture
def five_region_lut() -> AtlasLUT:
    """An atlas LUT with 5 regions: 3 cortical, 1 subcortical, 1 cerebellar."""
    return AtlasLUT(
        regions=[
            RegionInfo(index=1, name="LH_Vis_1", hemisphere="L", structure="cortex"),
            RegionInfo(index=2, name="RH_Vis_1", hemisphere="R", structure="cortex"),
            RegionInfo(index=3, name="LH_Default_1", hemisphere="L", structure="cortex"),
            RegionInfo(index=4, name="Thalamus_L", hemisphere="L", structure="subcortex"),
            RegionInfo(index=5, name="Cerebellum_R", hemisphere="R", structure="cerebellum"),
        ],
        atlas_name="TestAtlas5",
    )


@pytest.fixture
def synthetic_dseg() -> nib.Nifti1Image:
    """A 10×10×10 parcellation with 5 regions in known locations.

    Layout (z-slices):
        z=0,1: region 1 (20 voxels)
        z=2,3: region 2 (20 voxels)
        z=4,5: region 3 (20 voxels)
        z=6,7: region 4 (20 voxels)
        z=8,9: region 5 (20 voxels)

    Within each z-pair, only the first 10 voxels of the first row are labeled,
    giving exactly 20 voxels per region.
    """
    data = np.zeros((10, 10, 10), dtype=np.int32)
    for region_idx, z_start in enumerate([0, 2, 4, 6, 8], start=1):
        data[0, :, z_start] = region_idx
        data[0, :, z_start + 1] = region_idx
    return nib.Nifti1Image(data, affine=np.eye(4))


@pytest.fixture
def synthetic_scalar_uniform() -> nib.Nifti1Image:
    """A scalar map where every non-zero dseg voxel has value 0.5.

    Useful for verifying that mean == median == 0.5, std == 0, etc.
    """
    data = np.full((10, 10, 10), 0.5, dtype=np.float64)
    return nib.Nifti1Image(data, affine=np.eye(4))


@pytest.fixture
def synthetic_scalar_gradient() -> nib.Nifti1Image:
    """A scalar map with a known gradient along the y-axis.

    Values range from 0.1 to 1.0 across y=0..9, allowing predictable
    per-region statistics when combined with the synthetic dseg.
    """
    data = np.zeros((10, 10, 10), dtype=np.float64)
    for y in range(10):
        data[:, y, :] = 0.1 * (y + 1)  # 0.1, 0.2, ..., 1.0
    return nib.Nifti1Image(data, affine=np.eye(4))


@pytest.fixture
def bids_tree(tmp_path: Path) -> dict[str, Path]:
    """Create a minimal QSIRecon derivatives tree matching the real layout.

    Tree structure::

        qsirecon/
          atlases/
            atlas-TestAtlas5/
              atlas-TestAtlas5_dseg.tsv      # index + label columns
          sub-001/ses-01/dwi/
            sub-001_ses-01_space-T1w_seg-TestAtlas5_dseg.nii.gz
          derivatives/
            qsirecon-DTI/sub-001/ses-01/dwi/
              sub-001_ses-01_space-T1w_model-DTI_param-FA_dwimap.nii.gz
              sub-001_ses-01_space-T1w_model-DTI_param-MD_dwimap.nii.gz
            qsirecon-MRtrix3/sub-001/ses-01/dwi/
              sub-001_ses-01_space-T1w_model-ifod2_streamlines.tck.gz
              sub-001_ses-01_space-T1w_model-sift2_streamlineweights.csv

    Returns a dict with keys:
        root, dseg, scalar_fa, scalar_md, lut, tck, sift_weights, connectome
    """
    root = tmp_path / "qsirecon"
    affine = np.eye(4)
    shape = (10, 10, 10)

    # --- Atlas LUT in atlases/ directory (real QSIRecon layout) ---
    atlas_dir = root / "atlases" / "atlas-TestAtlas5"
    atlas_dir.mkdir(parents=True)
    lut_path = atlas_dir / "atlas-TestAtlas5_dseg.tsv"
    # Real QSIRecon TSVs use "index" and "label" columns (no explicit hemi/structure)
    lut_path.write_text(
        "index\tlabel\n"
        "1\tLH_Vis_1\n"
        "2\tRH_Vis_1\n"
        "3\tLH_Default_1\n"
        "4\tThalamus_L\n"
        "5\tCerebellum_R\n"
    )

    # --- Subject-space dseg (uses seg- entity, not atlas-) ---
    dwi_dir = root / "sub-001" / "ses-01" / "dwi"
    dwi_dir.mkdir(parents=True)
    dseg_data = np.zeros(shape, dtype=np.int32)
    for i, z in enumerate([0, 2, 4, 6, 8], start=1):
        dseg_data[0, :, z] = i
        dseg_data[0, :, z + 1] = i
    dseg_path = dwi_dir / "sub-001_ses-01_space-T1w_seg-TestAtlas5_dseg.nii.gz"
    nib.save(nib.Nifti1Image(dseg_data, affine), dseg_path)

    # --- Scalar maps in derivatives/qsirecon-DTI/ ---
    dti_dwi = root / "derivatives" / "qsirecon-DTI" / "sub-001" / "ses-01" / "dwi"
    dti_dwi.mkdir(parents=True)

    fa_data = np.random.default_rng(42).uniform(0.1, 0.9, shape).astype(np.float64)
    fa_path = dti_dwi / "sub-001_ses-01_space-T1w_model-DTI_param-FA_dwimap.nii.gz"
    nib.save(nib.Nifti1Image(fa_data, affine), fa_path)

    md_data = np.random.default_rng(43).uniform(0.0005, 0.002, shape).astype(np.float64)
    md_path = dti_dwi / "sub-001_ses-01_space-T1w_model-DTI_param-MD_dwimap.nii.gz"
    nib.save(nib.Nifti1Image(md_data, affine), md_path)

    # --- Tractography + SIFT2 weights in derivatives/qsirecon-MRtrix3/ ---
    mrtrix_dwi = root / "derivatives" / "qsirecon-MRtrix3" / "sub-001" / "ses-01" / "dwi"
    mrtrix_dwi.mkdir(parents=True)

    tck_path = mrtrix_dwi / "sub-001_ses-01_space-T1w_model-ifod2_streamlines.tck.gz"
    tck_path.write_bytes(b"")  # placeholder — content not needed for discovery tests

    sift_path = mrtrix_dwi / "sub-001_ses-01_space-T1w_model-sift2_streamlineweights.csv"
    np.savetxt(sift_path, np.ones(10), delimiter=",", fmt="%.6f")

    # --- Connectivity matrix (used directly by integration tests) ---
    conn_data = np.random.default_rng(44).integers(0, 100, (5, 5)).astype(float)
    conn_data = (conn_data + conn_data.T) / 2
    conn_path = dti_dwi / "sub-001_ses-01_space-T1w_seg-TestAtlas5_connectivity.csv"
    np.savetxt(conn_path, conn_data, delimiter=",", fmt="%.1f")

    return {
        "root": root,
        "dseg": dseg_path,
        "scalar_fa": fa_path,
        "scalar_md": md_path,
        "lut": lut_path,
        "tck": tck_path,
        "sift_weights": sift_path,
        "connectome": conn_path,
    }
