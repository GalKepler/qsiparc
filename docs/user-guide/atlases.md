# Atlases

QSIParc supports all atlases that QSIRecon has warped into subject diffusion space. No atlas-specific configuration is required — QSIParc discovers atlas parcellations and their label files automatically.

## How atlases work in QSIParc

QSIRecon registers brain atlases from MNI space into each subject's diffusion space during processing. QSIParc consumes these pre-warped files:

1. **`*_seg-{name}_dseg.nii.gz`** — Parcellation volume in subject T1w space
2. **`atlases/atlas-{name}/{name}_dseg.tsv`** — Label look-up table with region names

QSIParc never performs atlas registration — it is entirely downstream of QSIRecon.

## QSIRecon built-in atlases

QSIRecon ships with several atlases from the [4S parcellation series](https://github.com/PennLINC/AtlasPack):

| Atlas name | Parcels | Description |
|------------|---------|-------------|
| `4S156Parcels` | 156 | Multi-scale cortical + subcortical + cerebellar |
| `4S256Parcels` | 256 | |
| `4S456Parcels` | 456 | |
| `4S1056Parcels` | 1056 | Fine-grained; large connectivity matrices |
| `Schaefer2018N100Tian2020S2` | 100 cortical + subcortical | Schaefer cortical + Tian subcortical |
| `Schaefer2018N200Tian2020S2` | 200 cortical + subcortical | |
| `Schaefer2018N400Tian2020S2` | 400 cortical + subcortical | |

Availability depends on the QSIRecon workflow configuration used for your dataset. Check which atlases were produced:

```bash
ls <qsirecon_dir>/sub-001/ses-01/dwi/*_dseg.nii.gz
```

## Filtering by atlas

```bash
# Run only for one atlas
qsiparc /data/qsirecon /out --atlas Schaefer2018N100Tian2020S2

# Run for all discovered atlases (default)
qsiparc /data/qsirecon /out
```

## Region naming

Region names are loaded from the atlas TSV in `<qsirecon_dir>/atlases/atlas-{name}/`. The `region_name` column in the output TSV comes directly from this file.

### Hemisphere inference

If the atlas LUT does not include a `hemisphere` column, QSIParc infers it from the region name using common neuroimaging naming conventions:

| Pattern | Assignment |
|---------|-----------|
| Prefix: `lh_`, `lh-`, `left_`, `l_` | `L` |
| Suffix: `_lh`, `_left`, `_l` | `L` |
| Infix: `_lh_`, `_LH_` | `L` |
| Schaefer style: `7Networks_LH_Vis_1` | `L` |
| Same patterns with `rh`/`right`/`r` | `R` |
| No pattern matched | `bilateral` |

### Fallback LUT

If no TSV is found in the `atlases/` directory, QSIParc extracts unique integer labels from the NIfTI and assigns generic names:

```
region_0001, region_0002, ...
```

with `hemisphere = bilateral` for all regions. This is a last resort — meaningful downstream analysis requires proper region names.

## Atlas output directory

Each atlas gets its own subdirectory within the subject/session output:

```
sub-001/ses-01/dwi/
├── atlas-Schaefer2018N100Tian2020S2/
│   ├── ...diffmap.tsv
│   └── ...connmatrix.csv (×4)
├── atlas-4S156Parcels/
│   ├── ...diffmap.tsv
│   └── ...connmatrix.csv (×4)
└── ...
```

## Using a custom atlas

To use a custom atlas:

1. Register it to each subject's diffusion space (e.g. via ANTs or FSL) — this must be done outside QSIParc.
2. Name the parcellation file following the `*_seg-{custom_name}_dseg.nii.gz` convention and place it in the subject's `dwi/` directory within the QSIRecon derivatives tree.
3. Place the label TSV at `<qsirecon_dir>/atlases/atlas-{custom_name}/{custom_name}_dseg.tsv`.
4. Run QSIParc normally — it will discover the file automatically.
