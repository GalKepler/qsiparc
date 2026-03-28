# QSIParc — Project Specification

## Purpose

QSIParc extracts analysis-ready regional summaries and structural connectivity
matrices from QSIRecon outputs. It is one half of a two-package neuroimaging
feature extraction stack for the Strauss Neuroplasticity Brain Bank (SNBB), paired with
`fsatlas` (FreeSurfer morphometrics). The two packages share atlas naming
conventions but are otherwise independent.

## Scope

**In scope:**
- Parcellated diffusion scalar maps (FA, MD, RD, AD, plus model-specific: DKI, NODDI, MAPMRI)
- Structural connectivity matrices: four variants matching QSIRecon's workflow spec (`sift_invnodevol_radius2_count`, `radius2_meanlength`, `radius2_count`, `sift_radius2_count`)
- Support for QSIRecon's built-in atlas set (4S series: `4S156Parcels`, `4S256Parcels`, `4S456Parcels`, `4S1056Parcels`, and individual atlases like `Schaefer2018N100Tian2020S2`)
- BIDS-derivative output layout
- Long-format TSV for scalar maps; square matrix + JSON sidecar for connectomes

**Out of scope:**
- FreeSurfer surface-based extraction (that's `fsatlas`)
- Atlas warping/registration (we consume QSIRecon's already-warped atlas files)
- Tractography reconstruction (we consume QSIRecon's `.tck` files as input)

## Architecture

### Input expectations

QSIParc reads from a QSIRecon derivatives directory following BIDS layout:

```
qsirecon/
  sub-{label}/
    ses-{label}/
      dwi/
        sub-{label}_ses-{label}_space-T1w_desc-preproc_dwi.nii.gz
        sub-{label}_ses-{label}_space-T1w_atlas-{name}_dseg.nii.gz        # parcellation
        sub-{label}_ses-{label}_space-T1w_model-{name}_param-{name}.nii.gz # scalar maps
        sub-{label}_ses-{label}_algo-{algo}_desc-{desc}_tractography.tck   # tractography streamlines
        ...
```

The exact filenames vary by QSIRecon workflow/reconstruction spec. QSIParc
discovers files via BIDS-like glob patterns, not hardcoded paths.

### Output layout

```
<output-dir>/
  sub-{label}/
    ses-{label}/
      dwi/
        atlas-{atlas_name}/
          sub-{label}_ses-{label}_atlas-{atlas_name}_desc-{scalar}_diffmap.tsv
          sub-{label}_ses-{label}_atlas-{atlas_name}_connmatrix.csv
          sub-{label}_ses-{label}_atlas-{atlas_name}_connmatrix.json
```

### Diffusion scalar TSV format (long-format)

Each row = one region × one scalar map:

| column            | description                                        |
|-------------------|----------------------------------------------------|
| `region_index`    | Integer label from the atlas dseg                  |
| `region_name`     | Human-readable name (from atlas LUT)               |
| `hemisphere`      | `L`, `R`, or `bilateral`                           |
| `scalar`          | Name of the diffusion scalar (e.g. `FA`, `ICVF`)  |
| `mean`            | Arithmetic mean across voxels                      |
| `median`          | Median across voxels                               |
| `std`             | Standard deviation                                 |
| `iqr`             | Interquartile range                                |
| `skewness`        | Skewness of the voxel distribution                 |
| `kurtosis`        | Excess kurtosis                                    |
| `n_voxels`        | Number of voxels in the region                     |
| `coverage`        | Fraction of atlas-defined voxels with valid signal |

### Connectivity matrix format

- **CSV**: square N×N matrix, no row/column headers (region order matches atlas LUT)
- **JSON sidecar**: metadata including atlas name, edge weight type, region labels, and QSIRecon provenance

### Processing strategy

1. **Atlas dseg loading**: Load the atlas parcellation in subject diffusion space (already warped by QSIRecon). Parse LUT for region names.
2. **Scalar extraction**: For each scalar map, mask by each atlas region. Compute full distribution statistics per region using direct numpy operations (NOT nilearn's NiftiLabelsMasker — we need the raw voxel arrays for distribution stats).
3. **Connectome construction**: Build structural connectivity matrices from QSIRecon's `.tck` tractography files and the atlas parcellation using MRtrix3's `tck2connectome`. QSIRecon's workflow does *not* include a `tck2connectome` step — connectome construction is entirely QSIParc's responsibility. The atlas dseg NIfTI is the node image. QSIParc runs four `tck2connectome` calls per tractogram × atlas combination, each producing its own N×N CSV + JSON sidecar.

   The four `tck2connectome` calls, and their exact flags:

   **a) `sift_invnodevol_radius2_count`** — SIFT2-weighted, inverse-node-volume-scaled count
   ```
   tck2connectome <tck> <dseg> <out.csv> \
       -assignment_radial_search 2 \
       -scale_invnodevol \
       -symmetric \
       -stat_edge sum \
       -tck_weights_in <sift2_weights.csv>
   ```

   **b) `radius2_meanlength`** — unweighted mean streamline length per edge
   ```
   tck2connectome <tck> <dseg> <out.csv> \
       -assignment_radial_search 2 \
       -scale_length \
       -symmetric \
       -stat_edge mean
   ```

   **c) `radius2_count`** — raw streamline count (no SIFT2, no node-volume scaling)
   ```
   tck2connectome <tck> <dseg> <out.csv> \
       -assignment_radial_search 2 \
       -symmetric \
       -stat_edge sum
   ```

   **d) `sift_radius2_count`** — SIFT2-weighted count (no node-volume scaling)
   ```
   tck2connectome <tck> <dseg> <out.csv> \
       -assignment_radial_search 2 \
       -symmetric \
       -stat_edge sum \
       -tck_weights_in <sift2_weights.csv>
   ```

   Parameter reference (maps configuration shorthand to MRtrix3 CLI flags):
   - `search_radius: 2` → `-assignment_radial_search 2`
   - `scale_invnodevol: true` → `-scale_invnodevol`
   - `use_sift_weights: true` → `-tck_weights_in <weights_file>` (SIFT2 weights file is discovered adjacent to the `.tck`, typically `*_siftweights.csv`)
   - `length_scale: length` → `-scale_length`
   - `symmetric: true` → `-symmetric`
   - `stat_edge: sum|mean` → `-stat_edge sum` or `-stat_edge mean`
   - `zero_diagonal: false` → default behavior (no `-zero_diagonal` flag). Note: if this ever changes to `true`, add `-zero_diagonal`.

   The `measure` field from the YAML becomes the `desc-` entity in the output filename, e.g.:
   `sub-001_ses-01_atlas-Schaefer100_desc-sift_invnodevol_radius2_count_connmatrix.csv`

## Technology stack

- Python ≥ 3.10
- numpy, nibabel, scipy.stats (core computation)
- pandas (TSV assembly)
- Click (CLI)
- **MRtrix3** (external): `tck2connectome` for connectome construction — called via subprocess, must be on `$PATH`
- No heavy Python dependencies: no nilearn, no dipy, no QSIRecon-as-dependency

## Key design decisions

1. **Direct numpy masking** over nilearn abstractions — we need full voxel distributions, not just means.
2. **Long-format TSV** over wide-format — easier to filter, join, and analyze downstream; one file per atlas per session containing all scalars.
3. **No atlas warping** — QSIRecon already places atlases in subject space. We consume what it produces.
4. **File discovery over configuration** — glob for BIDS-named files rather than requiring users to enumerate inputs.
5. **Connectome computation via MRtrix3** — we shell out to `tck2connectome` rather than reimplementing streamline-to-node assignment in Python. QSIRecon produces the tractography (`.tck`) and SIFT2 weights but does not run `tck2connectome` — that step is entirely QSIParc's job. MRtrix3 is already present in any QSIRecon environment. QSIParc owns the full connectome pipeline: discovering `.tck` and SIFT2 weight files, running the four `tck2connectome` variants with the correct flags per measure, and packaging outputs with metadata.
6. **Fail-safe MRtrix3 dependency** — at startup and before each connectome job, verify `tck2connectome` is reachable. If MRtrix3 is not installed, scalar extraction still works; only connectome construction is skipped with a clear warning.

## CLI interface

```bash
# Extract all available atlases for all subjects
qsiparc /data/qsirecon /data/qsiparc-out

# Filter by atlas
qsiparc /data/qsirecon /data/qsiparc-out --atlas Schaefer2018N100Tian2020S2

# Filter by subject/session
qsiparc /data/qsirecon /data/qsiparc-out --participant-label sub-001 --session-label ses-01

# Specify which scalars to extract (default: all discovered)
qsiparc /data/qsirecon /data/qsiparc-out --scalars FA MD ICVF

# Dry run — show what would be processed
qsiparc /data/qsirecon /data/qsiparc-out --dry-run
```

## Error handling & logging

- Use `logging` with structured messages (subject, session, atlas in every log line)
- Warn but don't crash on: missing scalar maps, empty regions, shape mismatches, MRtrix3 not installed (skip connectomes gracefully)
- Fail hard on: missing atlas dseg, corrupted NIfTI headers, output path not writable, MRtrix3 subprocess returning nonzero (per-subject fail, not global crash)
- Return exit code 0 on success, 1 on partial failure (some subjects failed), 2 on total failure

## Testing strategy

- Unit tests for: scalar extraction math, file discovery globs, TSV assembly, LUT parsing
- Unit tests for: connectome module command-line assembly (verify the `tck2connectome` argument strings for each of the four measures without actually calling MRtrix3)
- Integration test with synthetic NIfTI data (small 10×10×10 volumes, 5-region atlas)
- Connectome integration tests should be marked `@pytest.mark.skipif` when MRtrix3 is not available on the test system
- No tests that require real QSIRecon outputs (those are too large for CI)
