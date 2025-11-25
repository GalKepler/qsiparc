from pathlib import Path

import nibabel as nib
import numpy as np

from qsiparc.parcellation.volume import parcellate_volume


def test_parcellate_volume_applies_mask(tmp_path: Path) -> None:
    atlas = np.array([[1, 1], [2, 2]], dtype=np.int16)
    scalar = np.array([[1.0, 3.0], [5.0, 7.0]], dtype=np.float32)
    mask = np.array([[0, 1], [0, 1]], dtype=np.int16)
    atlas_path = tmp_path / "atlas.nii.gz"
    scalar_path = tmp_path / "scalar.nii.gz"
    mask_path = tmp_path / "mask.nii.gz"
    nib.Nifti1Image(atlas, affine=np.eye(4)).to_filename(atlas_path)
    nib.Nifti1Image(scalar, affine=np.eye(4)).to_filename(scalar_path)
    nib.Nifti1Image(mask, affine=np.eye(4)).to_filename(mask_path)

    stats = parcellate_volume(atlas_path=atlas_path, scalar_path=scalar_path, metrics=("mean",), mask=mask_path)
    stats = stats.set_index("index")
    # Mask zeros out label voxels where mask == 0, so label 1 remains only at (0,1) with value 3.0; label 2 at (1,1) with value 7.0
    assert stats.loc["1", "mean"] == 3.0
    assert stats.loc["2", "mean"] == 7.0


def test_parcellate_volume_custom_metric(tmp_path: Path) -> None:
    atlas = np.array([[1, 1], [2, 2]], dtype=np.int16)
    scalar = np.array([[1.0, 3.0], [5.0, 7.0]], dtype=np.float32)
    atlas_path = tmp_path / "atlas.nii.gz"
    scalar_path = tmp_path / "scalar.nii.gz"
    nib.Nifti1Image(atlas, affine=np.eye(4)).to_filename(atlas_path)
    nib.Nifti1Image(scalar, affine=np.eye(4)).to_filename(scalar_path)

    def range_metric(arr: np.ndarray) -> float:
        return float(arr.max() - arr.min()) if arr.size else float("nan")

    stats = parcellate_volume(atlas_path=atlas_path, scalar_path=scalar_path, metrics=(("range", range_metric),))
    stats = stats.set_index("index")
    assert stats.loc["1", "range"] == 2.0
    assert stats.loc["2", "range"] == 2.0
