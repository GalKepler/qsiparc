# Diffusion Scalar Maps

QSIParc extracts region-level statistics from any diffusion scalar map produced by QSIRecon. This page describes the supported scalars, the statistics computed, and notes on interpretation.

## Supported models and scalars

QSIParc discovers scalar maps by glob pattern — any `*_space-ACPC_param-*_dwimap.nii.gz` file is processed. The following scalars are commonly produced by QSIRecon workflows:

### DTI — Diffusion Tensor Imaging

| Scalar | `param` entity | Description |
|--------|---------------|-------------|
| Fractional Anisotropy | `FA` | Degree of diffusion directionality (0–1). High FA = high white matter integrity. |
| Mean Diffusivity | `MD` | Average diffusion rate. Sensitive to cellularity, oedema, and myelination. |
| Radial Diffusivity | `RD` | Diffusivity perpendicular to the principal diffusion direction. Sensitive to myelin integrity. |
| Axial Diffusivity | `AD` | Diffusivity along the principal diffusion direction. |

### NODDI — Neurite Orientation Dispersion and Density Imaging

| Scalar | `param` entity | Description |
|--------|---------------|-------------|
| Intra-cellular volume fraction | `ICVF` | Neurite density index (NDI). Fraction of intra-neurite water. |
| Isotropic volume fraction | `ISOVF` | Free water fraction. |
| Orientation dispersion | `OD` | Angular dispersion of neurite orientations. |

### DKI — Diffusion Kurtosis Imaging

| Scalar | `param` entity | Description |
|--------|---------------|-------------|
| Mean Kurtosis | `MK` | Average non-Gaussianity of diffusion. |
| Axial Kurtosis | `AK` | Kurtosis along the principal direction. |
| Radial Kurtosis | `RK` | Kurtosis perpendicular to the principal direction. |

### MAPMRI — Mean Apparent Propagator MRI

| Scalar | `param` entity | Description |
|--------|---------------|-------------|
| Return-to-origin probability | `RTOP` | Probability of a water molecule returning to its origin. |
| Return-to-axis probability | `RTAP` | Axial restriction measure. |
| Return-to-plane probability | `RTPP` | Planar restriction measure. |
| Non-Gaussianity | `NG` | Deviation from Gaussian displacement. |

## Statistics computed

For each region × scalar combination, QSIParc computes the full voxel distribution using direct numpy masking:

| Statistic | Description | Notes |
|-----------|-------------|-------|
| `mean` | Arithmetic mean | NaN voxels excluded |
| `median` | 50th percentile | NaN voxels excluded |
| `std` | Standard deviation | |
| `iqr` | Q75 − Q25 | Robust spread measure |
| `skewness` | Pearson skewness | Positive = right tail |
| `kurtosis` | Excess kurtosis | 0 = Gaussian; positive = heavy-tailed |
| `n_voxels` | Count of valid voxels | Non-NaN voxels within the region mask |
| `coverage` | `n_voxels / n_atlas_voxels` | 1.0 = complete coverage |

!!! tip "Why full distributions?"
    Many diffusion scalars (especially FA) have non-Gaussian within-region distributions in large parcels. Mean alone can be misleading — skewness and kurtosis capture the shape of the distribution, and IQR provides a robust spread measure less sensitive to outliers than standard deviation.

## Zero-valued voxels

Some QSIRecon workflows produce scalar maps where background voxels outside the brain mask have value `0.0` rather than `NaN`. These zeros can corrupt statistics for regions near the brain boundary.

Use `--zero-is-missing` to treat `0.0` as missing data:

```bash
qsiparc /data/qsirecon /out --zero-is-missing
```

This sets all `0.0` voxels to `NaN` before extraction. Check whether this is appropriate for your data — some scalars (e.g. MD) legitimately have near-zero values in white matter.

## Coverage and missing data

The `coverage` column indicates what fraction of the atlas-defined region has valid signal:

- `coverage = 1.0`: All atlas voxels for this region have valid scalar values.
- `coverage < 1.0`: Some voxels are NaN (no signal). Common in regions near EPI distortion-affected areas.
- `coverage = 0.0`: The region is entirely outside the scalar map's valid mask. Statistics will be `NaN`.

!!! warning "Regions with zero coverage"
    Rows with `coverage = 0.0` will have `NaN` for all statistics. Filter these out before analysis:
    ```python
    df = df[df["coverage"] > 0]
    ```

## 4D scalar maps

If a scalar NIfTI is 4D (multiple volumes), QSIParc uses only the first volume and logs a warning. This is a fallback — verify that the input file is correct.
