"""Shared test fixtures: synthetic NIfTI data and BIDS directory trees.

These fixtures produce small (10×10×10) volumes with known values so that
extraction results can be verified deterministically.
"""

from __future__ import annotations

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
    """Create a minimal BIDS-like QSIRecon derivatives tree on disk.

    Returns a dict with keys: 'root', 'dseg', 'scalar_fa', 'scalar_md', 'connectome'.
    """
    root = tmp_path / "qsirecon"
    dwi_dir = root / "sub-001" / "ses-01" / "dwi"
    dwi_dir.mkdir(parents=True)

    affine = np.eye(4)
    shape = (10, 10, 10)

    # dseg
    dseg_data = np.zeros(shape, dtype=np.int32)
    for i, z in enumerate([0, 2, 4, 6, 8], start=1):
        dseg_data[0, :, z] = i
        dseg_data[0, :, z + 1] = i
    dseg_path = dwi_dir / "sub-001_ses-01_space-T1w_atlas-TestAtlas5_dseg.nii.gz"
    nib.save(nib.Nifti1Image(dseg_data, affine), dseg_path)

    # FA scalar
    fa_data = np.random.default_rng(42).uniform(0.1, 0.9, shape).astype(np.float64)
    fa_path = dwi_dir / "sub-001_ses-01_space-T1w_model-DTI_param-FA.nii.gz"
    nib.save(nib.Nifti1Image(fa_data, affine), fa_path)

    # MD scalar
    md_data = np.random.default_rng(43).uniform(0.0005, 0.002, shape).astype(np.float64)
    md_path = dwi_dir / "sub-001_ses-01_space-T1w_model-DTI_param-MD.nii.gz"
    nib.save(nib.Nifti1Image(md_data, affine), md_path)

    # Connectivity matrix (5×5)
    conn_data = np.random.default_rng(44).integers(0, 100, (5, 5)).astype(float)
    conn_data = (conn_data + conn_data.T) / 2  # symmetrize
    conn_path = dwi_dir / "sub-001_ses-01_algo-CSD_atlas-TestAtlas5_connectivity.csv"
    np.savetxt(conn_path, conn_data, delimiter=",", fmt="%.1f")

    # LUT file
    lut_path = dwi_dir / "sub-001_ses-01_space-T1w_atlas-TestAtlas5_dseg.tsv"
    lut_path.write_text(
        "index\tname\themisphere\tstructure\n"
        "1\tLH_Vis_1\tL\tcortex\n"
        "2\tRH_Vis_1\tR\tcortex\n"
        "3\tLH_Default_1\tL\tcortex\n"
        "4\tThalamus_L\tL\tsubcortex\n"
        "5\tCerebellum_R\tR\tcerebellum\n"
    )

    return {
        "root": root,
        "dseg": dseg_path,
        "scalar_fa": fa_path,
        "scalar_md": md_path,
        "connectome": conn_path,
        "lut": lut_path,
    }
