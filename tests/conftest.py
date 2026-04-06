"""Shared test fixtures: synthetic NIfTI data and BIDS directory trees.

These fixtures produce small (10x10x10) volumes with known values so that
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
            RegionInfo(index=1, name="LH_Vis_1", hemisphere="L"),
            RegionInfo(index=2, name="RH_Vis_1", hemisphere="R"),
            RegionInfo(index=3, name="LH_Default_1", hemisphere="L"),
            RegionInfo(index=4, name="Thalamus_L", hemisphere="L"),
            RegionInfo(index=5, name="Cerebellum_R", hemisphere="R"),
        ],
        atlas_name="TestAtlas5",
    )


@pytest.fixture
def synthetic_dseg() -> nib.Nifti1Image:
    """A 10x10x10 parcellation with 5 regions in known locations.

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
              sub-001_ses-01_space-ACPC_model-DTI_param-FA_dwimap.nii.gz
              sub-001_ses-01_space-ACPC_model-DTI_param-MD_dwimap.nii.gz
              sub-001_ses-01_space-MNI152NLin2009cAsym_model-DTI_param-FA_dwimap.nii.gz
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
    fa_path = dti_dwi / "sub-001_ses-01_space-ACPC_model-DTI_param-FA_dwimap.nii.gz"
    nib.save(nib.Nifti1Image(fa_data, affine), fa_path)

    md_data = np.random.default_rng(43).uniform(0.0005, 0.002, shape).astype(np.float64)
    md_path = dti_dwi / "sub-001_ses-01_space-ACPC_model-DTI_param-MD_dwimap.nii.gz"
    nib.save(nib.Nifti1Image(md_data, affine), md_path)

    # MNI-space map — should be excluded by discover_scalar_maps
    mni_fa_data = np.random.default_rng(99).uniform(0.1, 0.9, shape).astype(np.float64)
    mni_fa_name = (
        "sub-001_ses-01_space-MNI152NLin2009cAsym_model-DTI_param-FA_dwimap.nii.gz"
    )
    mni_fa_path = dti_dwi / mni_fa_name
    nib.save(nib.Nifti1Image(mni_fa_data, affine), mni_fa_path)

    # --- Tractography + SIFT2 weights in derivatives/qsirecon-MRtrix3/ ---
    mrtrix_dwi = (
        root / "derivatives" / "qsirecon-MRtrix3" / "sub-001" / "ses-01" / "dwi"
    )
    mrtrix_dwi.mkdir(parents=True)

    tck_path = mrtrix_dwi / "sub-001_ses-01_space-T1w_model-ifod2_streamlines.tck.gz"
    tck_path.write_bytes(b"")  # placeholder — content not needed for discovery tests

    sift_path = (
        mrtrix_dwi / "sub-001_ses-01_space-T1w_model-sift2_streamlineweights.csv"
    )
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


@pytest.fixture
def qsiparc_output_tree(tmp_path: Path) -> dict[str, Path]:
    """Create a minimal qsiparc output directory with diffmap TSVs and connectome files.

    Structure::

        qsiparc_out/
          sub-001/ses-01/dwi/atlas-TestAtlas5/
            sub-001_ses-01_atlas-TestAtlas5_param-FA_diffmap.tsv
            sub-001_ses-01_atlas-TestAtlas5_param-FA_diffmap.json
            sub-001_ses-01_atlas-TestAtlas5_desc-radius2count_connmatrix.csv
            sub-001_ses-01_atlas-TestAtlas5_desc-radius2count_connmatrix.json
            sub-001_ses-01_atlas-TestAtlas5_desc-radius2meanlength_connmatrix.csv
            sub-001_ses-01_atlas-TestAtlas5_desc-radius2meanlength_connmatrix.json
          sub-002/ses-01/dwi/atlas-TestAtlas5/
            (same files for sub-002)

    Returns a dict with keys:
        root, group_dir, atlas_dir_001, atlas_dir_002
    """
    root = tmp_path / "qsiparc_out"
    region_labels = [
        "LH_Vis_1",
        "RH_Vis_1",
        "LH_Default_1",
        "Thalamus_L",
        "Cerebellum_R",
    ]
    n_regions = len(region_labels)
    rng = np.random.default_rng(0)

    def _make_diffmap_tsv(
        atlas_dir: Path, subject: str, session: str, scalar: str
    ) -> None:
        rows = []
        for i, name in enumerate(region_labels, start=1):
            hemi = (
                "L"
                if name.startswith("LH")
                else ("R" if name.startswith("RH") else "bilateral")
            )
            rows.append(
                {
                    "region_index": i,
                    "region_name": name,
                    "hemisphere": hemi,
                    "scalar": scalar,
                    "mean": round(rng.uniform(0.1, 0.9), 4),
                    "median": round(rng.uniform(0.1, 0.9), 4),
                    "std": round(rng.uniform(0.01, 0.1), 4),
                    "iqr": round(rng.uniform(0.01, 0.1), 4),
                    "skewness": round(rng.uniform(-1, 1), 4),
                    "kurtosis": round(rng.uniform(-1, 1), 4),
                    "n_voxels": int(rng.integers(10, 50)),
                    "coverage": round(rng.uniform(0.8, 1.0), 4),
                }
            )
        import pandas as pd

        df = pd.DataFrame(rows)
        stem = f"{subject}_{session}_atlas-TestAtlas5_param-{scalar}_diffmap"
        tsv_path = atlas_dir / f"{stem}.tsv"
        json_path = atlas_dir / f"{stem}.json"
        df.to_csv(tsv_path, sep="\t", index=False)
        json_path.write_text(
            json.dumps(
                {
                    "subject": subject,
                    "session": session,
                    "atlas_name": "TestAtlas5",
                    "scalar_name": scalar,
                    "generated_by": {"name": "QSIParc", "version": "0.1.0"},
                }
            )
        )

    def _make_connmatrix(
        atlas_dir: Path, subject: str, session: str, measure: str
    ) -> None:
        matrix = rng.integers(0, 100, (n_regions, n_regions)).astype(float)
        matrix = (matrix + matrix.T) / 2  # make symmetric
        stem = f"{subject}_{session}_atlas-TestAtlas5_desc-{measure}_connmatrix"
        csv_path = atlas_dir / f"{stem}.csv"
        json_path = atlas_dir / f"{stem}.json"
        np.savetxt(csv_path, matrix, delimiter=",", fmt="%.2f")
        json_path.write_text(
            json.dumps(
                {
                    "atlas_name": "TestAtlas5",
                    "measure": measure,
                    "n_regions": n_regions,
                    "region_labels": region_labels,
                    "symmetric": True,
                }
            )
        )

    atlas_dirs: dict[str, Path] = {}
    for subject in ("sub-001", "sub-002"):
        atlas_dir = root / subject / "ses-01" / "dwi" / "atlas-TestAtlas5"
        atlas_dir.mkdir(parents=True)
        atlas_dirs[subject] = atlas_dir
        for scalar in ("FA", "MD"):
            _make_diffmap_tsv(atlas_dir, subject, "ses-01", scalar)
        for measure in ("radius2count", "radius2meanlength"):
            _make_connmatrix(atlas_dir, subject, "ses-01", measure)

    return {
        "root": root,
        "group_dir": root / "group",
        "atlas_dir_001": atlas_dirs["sub-001"],
        "atlas_dir_002": atlas_dirs["sub-002"],
        "region_labels": region_labels,
        "n_regions": n_regions,
    }
