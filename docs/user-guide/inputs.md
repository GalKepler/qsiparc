# Input Layout

QSIParc reads from a QSIRecon derivatives directory. This page describes the expected directory structure and file naming conventions.

## Directory structure

``` annotate
<qsirecon_dir>/
├── atlases/                                          # (1)!
│   └── atlas-{name}/
│       └── {name}_dseg.tsv
├── sub-{label}/
│   └── ses-{label}/
│       └── dwi/
│           └── sub-{label}_ses-{label}_space-T1w_seg-{atlas}_dseg.nii.gz   # (2)!
└── derivatives/
    └── qsirecon-{workflow}/                          # (3)!
        └── sub-{label}/
            └── ses-{label}/
                └── dwi/
                    ├── sub-{label}_ses-{label}_space-ACPC_param-{scalar}_dwimap.nii.gz  # (4)!
                    ├── sub-{label}_ses-{label}_algo-{algo}_desc-{desc}_streamlines.tck.gz  # (5)!
                    └── sub-{label}_ses-{label}_algo-{algo}_desc-{desc}_streamlineweights.csv  # (6)!
```

1. **Atlas LUT directory** — QSIRecon ships TSV label files here. QSIParc uses these for human-readable region names.
2. **Atlas parcellation (dseg)** — Atlas in subject T1w diffusion space, already warped by QSIRecon.
3. **Workflow subdirectories** — There may be multiple `qsirecon-*` directories (one per reconstruction spec). QSIParc discovers scalar maps across all of them.
4. **Diffusion scalar maps** — Any `*_dwimap.nii.gz` in ACPC space with a `param` entity is discovered.
5. **Tractography** — Compressed MRtrix3 streamline files (`*.tck.gz`).
6. **SIFT2 weights** — Streamline weight CSV produced by SIFT2, adjacent to the tractogram.

## Atlas parcellations (dseg)

The glob pattern used:

```
{qsirecon_dir}/{sub-*}/{ses-*}/dwi/*_dseg.nii.gz
```

Files must have a `seg-` BIDS entity in the filename (e.g. `seg-Schaefer2018N100Tian2020S2`). Files without this entity are skipped.

### Atlas LUT files

QSIParc looks for the atlas TSV at:

```
{qsirecon_dir}/atlases/atlas-{atlas_name}/{atlas_name}_dseg.tsv
```

If the TSV is not found, QSIParc falls back to extracting unique integer labels from the NIfTI and assigns generic names (`region_0001`, etc.). Always provide the TSV for meaningful region names.

Supported LUT formats:

| Format | Description |
|--------|-------------|
| **TSV** | Tab-separated with `index`/`id` and `name`/`label` columns (QSIRecon standard) |
| **JSON** | `{"1": "RegionName", ...}` or `[{"index": 1, "name": "...", ...}]` |
| **FreeSurfer LUT** | Space-separated: `index name R G B A` |

## Diffusion scalar maps

The glob pattern used:

```
{qsirecon_dir}/derivatives/qsirecon-*/{sub}/{ses}/dwi/*_dwimap.nii.gz
```

Files are filtered to ACPC space (`space-ACPC` entity required). The scalar name is taken from the `param` entity (e.g. `param-FA`), falling back to the `desc` entity.

### Supported scalars

QSIParc is not prescriptive about which scalars are present — it discovers whatever QSIRecon produced. Common examples:

| Scalar | Model | Description |
|--------|-------|-------------|
| `FA` | DTI | Fractional anisotropy |
| `MD` | DTI | Mean diffusivity |
| `RD` | DTI | Radial diffusivity |
| `AD` | DTI | Axial diffusivity |
| `ICVF` | NODDI | Intra-cellular volume fraction |
| `ISOVF` | NODDI | Isotropic volume fraction |
| `OD` | NODDI | Orientation dispersion |
| `MK` | DKI | Mean kurtosis |
| `AK` | DKI | Axial kurtosis |
| `RK` | DKI | Radial kurtosis |
| `RTOP` | MAPMRI | Return-to-origin probability |
| `RTAP` | MAPMRI | Return-to-axis probability |
| `RTPP` | MAPMRI | Return-to-plane probability |

See [Diffusion Scalars](scalars.md) for a full description.

## Tractography files

The glob pattern used:

```
{qsirecon_dir}/derivatives/qsirecon-*/{sub}/{ses}/dwi/*_streamlines.tck.gz
```

MRtrix3 does not support gzip-compressed tractograms directly; QSIParc decompresses `.tck.gz` to a temporary `.tck` before calling `tck2connectome`, then cleans up.

## SIFT2 weight files

The glob pattern used:

```
{qsirecon_dir}/derivatives/qsirecon-*/{sub}/{ses}/dwi/*_streamlineweights.csv
```

QSIParc looks for SIFT2 weight files adjacent to each tractogram (same directory). The two SIFT2-weighted connectome measures (`sift_invnodevol_radius2_count` and `sift_radius2_count`) are skipped for a given tractogram if no weight file is found nearby.

## Filtering inputs

Use CLI flags to restrict processing:

```bash
# Single subject
qsiparc /data/qsirecon /out --participant-label sub-001

# Single session
qsiparc /data/qsirecon /out --session-label ses-01

# Single atlas
qsiparc /data/qsirecon /out --atlas Schaefer2018N100Tian2020S2

# Specific scalars only
qsiparc /data/qsirecon /out --scalars FA MD ICVF
```

Labels can be specified with or without the BIDS prefix (`sub-001` or `001`, `ses-01` or `01`).
