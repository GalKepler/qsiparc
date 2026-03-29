# Output Format

QSIParc writes outputs in a BIDS-derivative layout. This page describes every file type produced.

## Directory structure

``` annotate
<output_dir>/
├── dataset_description.json                          # (1)!
└── sub-{label}/
    └── ses-{label}/
        └── dwi/
            └── atlas-{atlas_name}/
                ├── sub-{label}_ses-{label}_atlas-{atlas_name}_..._diffmap.tsv   # (2)!
                ├── sub-{label}_ses-{label}_atlas-{atlas_name}_..._diffmap.json  # (3)!
                ├── sub-{label}_ses-{label}_..._desc-sift_invnodevol_radius2_count_connmatrix.csv   # (4)!
                ├── sub-{label}_ses-{label}_..._desc-sift_invnodevol_radius2_count_connmatrix.json
                ├── sub-{label}_ses-{label}_..._desc-radius2_meanlength_connmatrix.csv
                ├── sub-{label}_ses-{label}_..._desc-radius2_meanlength_connmatrix.json
                ├── sub-{label}_ses-{label}_..._desc-radius2_count_connmatrix.csv
                ├── sub-{label}_ses-{label}_..._desc-radius2_count_connmatrix.json
                ├── sub-{label}_ses-{label}_..._desc-sift_radius2_count_connmatrix.csv
                └── sub-{label}_ses-{label}_..._desc-sift_radius2_count_connmatrix.json
```

1. **Root-level BIDS dataset description**
2. **Diffusion scalar TSV** — long-format, one row per region × scalar
3. **Diffusion scalar JSON sidecar** — provenance metadata for the TSV
4. **Connectivity matrix CSV** — one per measure per tractogram × atlas pair

## dataset_description.json

Written once at the root of the output directory. Follows BIDS 1.9.0 derivative format:

```json
{
  "Name": "QSIParc — Parcellated Diffusion Features",
  "BIDSVersion": "1.9.0",
  "DatasetType": "derivative",
  "GeneratedBy": [
    {
      "Name": "QSIParc",
      "Description": "Parcellated diffusion scalar extraction and connectivity repackaging from QSIRecon outputs.",
      "CodeURL": "https://github.com/snbb/qsiparc"
    }
  ]
}
```

## Diffusion scalar TSV (`*_diffmap.tsv`)

One file per atlas per session, containing all extracted scalars stacked in long format.

### Filename

```
sub-{label}_ses-{label}_atlas-{atlas_name}_software-{workflow}_{source_entities}_diffmap.tsv
```

- `software-{workflow}`: QSIRecon workflow name (e.g. `software-AMICONODDI`). Omitted if not determinable from the path.
- `{source_entities}`: BIDS key-value pairs from the source scalar file, excluding `sub` and `ses`.

### Columns

| Column | Type | Description |
|--------|------|-------------|
| `region_index` | `int` | Integer label from the atlas dseg |
| `region_name` | `str` | Human-readable name from the atlas LUT |
| `hemisphere` | `str` | `L`, `R`, or `bilateral` |
| `scalar` | `str` | Diffusion scalar name (e.g. `FA`, `ICVF`) |
| `mean` | `float` | Arithmetic mean across valid voxels |
| `median` | `float` | Median |
| `std` | `float` | Standard deviation |
| `iqr` | `float` | Interquartile range (Q75 − Q25) |
| `skewness` | `float` | Pearson skewness |
| `kurtosis` | `float` | Excess kurtosis |
| `n_voxels` | `int` | Number of valid (non-NaN) voxels in the region |
| `coverage` | `float` | Fraction of atlas-defined voxels with valid signal (0–1) |

!!! note "Long format"
    Each row represents one region × one scalar combination. A session with 100 atlas regions and 12 scalars produces 1,200 rows in a single TSV.

### Example rows

```
region_index  region_name                hemisphere  scalar  mean    median  std     iqr     skewness  kurtosis  n_voxels  coverage
1             LH_Vis_1                   L           FA      0.4218  0.4195  0.0823  0.1041  0.1548    -0.3241   847       0.9811
2             LH_Vis_2                   L           FA      0.3974  0.3901  0.0791  0.0998  0.2103    -0.2987   623       0.9654
...
1             LH_Vis_1                   L           MD      0.0008  0.0008  0.0001  0.0001  0.4231    0.8714    847       0.9811
```

### Loading in Python

```python
import pandas as pd

df = pd.read_csv("...diffmap.tsv", sep="\t")

# All FA values, left hemisphere
fa = df[(df["scalar"] == "FA") & (df["hemisphere"] == "L")]

# Pivot to wide format (regions × scalars)
wide = df.pivot_table(index="region_name", columns="scalar", values="mean")
```

## Diffusion scalar JSON sidecar (`*_diffmap.json`)

Full provenance for each TSV file.

```json
{
  "subject": "sub-001",
  "session": "ses-01",
  "atlas_name": "Schaefer2018N100Tian2020S2",
  "atlas_dseg": "/data/qsirecon/sub-001/ses-01/dwi/...dseg.nii.gz",
  "lut_file": "/data/qsirecon/atlases/atlas-Schaefer2018N100Tian2020S2/...dseg.tsv",
  "scalar_name": "FA",
  "source_file": "/data/qsirecon/derivatives/qsirecon-AMICONODDI/sub-001/ses-01/dwi/...dwimap.nii.gz",
  "source_entities": {"sub": "001", "ses": "01", "space": "ACPC", "param": "FA"},
  "software": "AMICONODDI",
  "processing": {
    "zero_is_missing": false,
    "stat_tier": "extended"
  },
  "generated_by": {
    "name": "QSIParc",
    "version": "0.1.0",
    "timestamp": "2026-03-29T10:23:15.123456+00:00"
  }
}
```

## Connectivity matrix CSV (`*_connmatrix.csv`)

Symmetric N×N matrix. Rows and columns correspond to atlas regions in the order defined by the atlas LUT. No row/column headers.

```
0.0,4.21,8.73,...
4.21,0.0,12.4,...
8.73,12.4,0.0,...
...
```

!!! warning "No headers"
    The CSV has no header row or row index. Region correspondence is defined by the paired JSON sidecar's `region_labels` field.

### Loading in Python

```python
import numpy as np
import json

matrix = np.loadtxt("...connmatrix.csv", delimiter=",")

with open("...connmatrix.json") as f:
    meta = json.load(f)

labels = meta["region_labels"]  # list of region names, same order as matrix rows/cols
```

### Four measures

| Measure (`desc-`) | Description | SIFT2 weights |
|-------------------|-------------|---------------|
| `sift_invnodevol_radius2_count` | SIFT2-weighted count, normalised by inverse node volume | Required |
| `radius2_meanlength` | Mean streamline length per edge | Not used |
| `radius2_count` | Raw streamline count | Not used |
| `sift_radius2_count` | SIFT2-weighted raw count | Required |

Measures requiring SIFT2 weights are skipped (with a warning) when no weight file is found adjacent to the tractogram.

## Connectivity matrix JSON sidecar (`*_connmatrix.json`)

```json
{
  "atlas_name": "Schaefer2018N100Tian2020S2",
  "measure": "sift_invnodevol_radius2_count",
  "n_regions": 100,
  "region_labels": ["LH_Vis_1", "LH_Vis_2", ...],
  "symmetric": true,
  "source_tck": "/data/qsirecon/derivatives/.../...streamlines.tck.gz",
  "source_dseg": "/data/qsirecon/sub-001/ses-01/dwi/...dseg.nii.gz",
  "sift_weights": "/data/qsirecon/derivatives/.../...streamlineweights.csv",
  "tck2connectome_cmd": ["tck2connectome", "...", "..."]
}
```

The `tck2connectome_cmd` field contains the exact command that was run, enabling full reproducibility.
