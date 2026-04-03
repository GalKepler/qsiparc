# Quick Start

This guide walks through a typical QSIParc run from start to finish.

## 1. Confirm your QSIRecon output looks right

QSIParc expects a QSIRecon derivatives directory with the standard BIDS layout:

```
/data/qsirecon/
├── atlases/
│   └── atlas-Schaefer2018N100Tian2020S2/
│       └── Schaefer2018N100Tian2020S2_dseg.tsv
├── sub-001/
│   └── ses-01/
│       └── dwi/
│           ├── sub-001_ses-01_space-T1w_seg-Schaefer2018N100Tian2020S2_dseg.nii.gz
│           ...
└── derivatives/
    └── qsirecon-AMICONODDI/
        └── sub-001/
            └── ses-01/
                └── dwi/
                    ├── sub-001_ses-01_space-ACPC_param-ICVF_dwimap.nii.gz
                    ├── sub-001_ses-01_space-ACPC_param-FA_dwimap.nii.gz
                    └── sub-001_ses-01_algo-iFOD2_desc-iFOD2-1M_streamlines.tck.gz
```

See [Input Layout](user-guide/inputs.md) for the full specification.

## 2. Dry run first

Always start with `--dry-run` to confirm QSIParc can find your files:

```bash
qsiparc /data/qsirecon /data/qsiparc-out --dry-run
```

Example output:
```
Found 4 atlas parcellation(s):
  sub-001/ses-01 atlas=Schaefer2018N100Tian2020S2  lut=yes → /data/qsirecon/sub-001/ses-01/dwi/...
  sub-001/ses-02 atlas=Schaefer2018N100Tian2020S2  lut=yes → /data/qsirecon/sub-001/ses-02/dwi/...
  sub-002/ses-01 atlas=Schaefer2018N100Tian2020S2  lut=yes → /data/qsirecon/sub-002/ses-01/dwi/...
  sub-002/ses-02 atlas=Schaefer2018N100Tian2020S2  lut=yes → /data/qsirecon/sub-002/ses-02/dwi/...
```

If `lut=no` appears, QSIParc will fall back to extracting region labels directly from the NIfTI — region names will be generic (`region_0001`, etc.). Place the atlas TSV in `<qsirecon_dir>/atlases/atlas-<name>/` to fix this.

## 3. Run on a single subject first

```bash
qsiparc /data/qsirecon /data/qsiparc-out \
    --participant-label sub-001 \
    --session-label ses-01 \
    -v
```

The `-v` flag enables INFO-level logging so you can see what is happening:
```
10:23:01 [INFO   ] qsiparc.discover | Discovered 1 dseg files (filters: participant=sub-001, session=ses-01, atlas=None)
10:23:01 [INFO   ] qsiparc.discover | Discovered 12 scalar maps for sub-001/ses-01 (filter: None)
10:23:02 [INFO   ] qsiparc.extract  | Extracted FA for 100 regions (atlas=Schaefer2018N100Tian2020S2)
...
10:23:15 [INFO   ] qsiparc.cli      | sub-001/ses-01/atlas-Schaefer2018N100Tian2020S2 | Done

QSIParc complete: 1 succeeded, 0 failed out of 1 parcellations.
```

## 4. Check the output

```bash
ls /data/qsiparc-out/sub-001/ses-01/dwi/atlas-Schaefer2018N100Tian2020S2/
```

```
sub-001_ses-01_atlas-Schaefer2018N100Tian2020S2_software-AMICONODDI_...diffmap.tsv
sub-001_ses-01_atlas-Schaefer2018N100Tian2020S2_software-AMICONODDI_...diffmap.json
sub-001_ses-01_atlas-Schaefer2018N100Tian2020S2_...desc-sift_invnodevol_radius2_count_connmatrix.csv
sub-001_ses-01_atlas-Schaefer2018N100Tian2020S2_...desc-sift_invnodevol_radius2_count_connmatrix.json
... (3 more connmatrix pairs)
```

Load the diffusion scalar TSV in Python:

```python
import pandas as pd

df = pd.read_csv(
    "qsiparc-out/sub-001/ses-01/dwi/atlas-Schaefer2018N100Tian2020S2/...diffmap.tsv",
    sep="\t",
)

# Filter to FA in left hemisphere
fa_left = df[(df["scalar"] == "FA") & (df["hemisphere"] == "L")]
print(fa_left[["region_name", "mean", "std", "n_voxels"]].head())
```

## 5. Run on all subjects

```bash
qsiparc /data/qsirecon /data/qsiparc-out -v
```

QSIParc processes subjects in parallel (one per atlas parcellation found). Progress is logged per subject/session/atlas. The final summary line tells you how many succeeded:

```
QSIParc complete: 48 succeeded, 0 failed out of 48 parcellations.
```

Exit code `0` means all succeeded. `1` means partial failure (some subjects had errors). `2` means total failure.

## Common options

| Option | Example | Purpose |
|--------|---------|---------|
| `--atlas` | `-a 4S156Parcels -a 4S256Parcels` | Restrict to one or more atlases (repeatable) |
| `--scalars` | `--scalars FA MD ICVF` | Only specific scalars |
| `--zero-is-missing` | | Treat 0.0 voxels as NaN |
| `--stat-tier` | `--stat-tier core` | Fewer statistics columns |
| `--dry-run` | | Preview without processing |
| `-v` / `-vv` | | INFO / DEBUG logging |

See [CLI Reference](user-guide/cli.md) for the full option list.
