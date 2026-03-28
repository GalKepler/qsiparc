# `qsiparc.extract`

Per-region diffusion scalar extraction using direct numpy masking.

## Constants

### `OUTPUT_COLUMNS`

```python
OUTPUT_COLUMNS = [
    "region_index", "region_name", "hemisphere",
    "scalar",
    "mean", "median", "std", "iqr", "skewness", "kurtosis",
    "n_voxels", "coverage",
]
```

The ordered column list in every `ExtractionResult.stats_df`.

## Classes

### `ExtractionResult`

Container for one scalar × one atlas extraction.

```python
@dataclass(frozen=True)
class ExtractionResult:
    scalar_name: str       # e.g. "FA"
    atlas_name: str        # e.g. "Schaefer2018N100Tian2020S2"
    stats_df: pd.DataFrame # One row per region, columns = OUTPUT_COLUMNS
```

---

## Functions

### `extract_scalar_map`

```python
def extract_scalar_map(
    scalar_path: str | Path | nib.Nifti1Image,
    dseg_path: str | Path | nib.Nifti1Image,
    lut: AtlasLUT,
    scalar_name: str,
    stat_tier: str = "extended",
    zero_is_missing: bool = False,
) -> ExtractionResult
```

Extract per-region statistics from a scalar NIfTI map.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scalar_path` | `str \| Path \| Nifti1Image` | — | Scalar map NIfTI (FA, MD, ICVF, …) |
| `dseg_path` | `str \| Path \| Nifti1Image` | — | Atlas parcellation dseg NIfTI (already in subject space) |
| `lut` | `AtlasLUT` | — | Region look-up table for labeling output rows |
| `scalar_name` | `str` | — | Written to the `scalar` column (e.g. `"FA"`) |
| `stat_tier` | `str` | `"extended"` | Statistic tier passed to the parcellator |
| `zero_is_missing` | `bool` | `False` | If `True`, treat `0.0` voxels as NaN before extraction |

**Returns:** `ExtractionResult` with a DataFrame of one row per atlas region.

**Raises:**

| Exception | Condition |
|-----------|-----------|
| `ValueError` | Scalar and dseg 3D shapes do not match |

**Example:**

```python
from pathlib import Path
from qsiparc.discover import load_lut_for_dseg, discover_dseg_files
from qsiparc.extract import extract_scalar_map

qsirecon_dir = Path("/data/qsirecon")
dseg_files = discover_dseg_files(qsirecon_dir, participant_label="sub-001")
dseg = dseg_files[0]
lut = load_lut_for_dseg(dseg)

result = extract_scalar_map(
    scalar_path="/data/qsirecon/derivatives/qsirecon-AMICONODDI/sub-001/ses-01/dwi/"
                "sub-001_ses-01_space-ACPC_param-FA_dwimap.nii.gz",
    dseg_path=dseg.path,
    lut=lut,
    scalar_name="FA",
    zero_is_missing=True,
)

print(result.stats_df.head())
#    region_index  region_name  hemisphere  scalar  mean    ...
# 0  1             LH_Vis_1     L           FA      0.4218  ...
```

**Notes:**

- Both scalar and dseg must have the same 3D shape. QSIRecon guarantees this when both are in subject T1w space.
- If the scalar is 4D, only the first volume is used (with a warning).
- `n_voxels` counts non-NaN voxels within the region mask. `coverage` is `n_voxels / n_atlas_voxels`.
- Regions with zero valid voxels produce `NaN` statistics.

---

### `merge_extraction_results`

```python
def merge_extraction_results(results: list[ExtractionResult]) -> pd.DataFrame
```

Stack multiple `ExtractionResult` objects into a single long-format DataFrame.

```python
from qsiparc.extract import merge_extraction_results

fa_result = extract_scalar_map(..., scalar_name="FA")
md_result = extract_scalar_map(..., scalar_name="MD")

combined = merge_extraction_results([fa_result, md_result])
# combined has len(lut) * 2 rows
```

Returns an empty DataFrame if the input list is empty.
