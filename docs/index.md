<p align="center">
  <img src="assets/qsiparc_logo.png" alt="qsiparc logo" width="400">
</p>

# QSIParc

**Parcellated diffusion feature extraction and structural connectome construction from [QSIRecon](https://qsirecon.readthedocs.io/) outputs.**

QSIParc is one half of the Strauss Neuroplasticity Brain Bank ([SNBB](https://www.snbb.sites.tau.ac.il/)) neuroimaging feature extraction stack, paired with **fsatlas** (FreeSurfer morphometrics). It reads atlas parcellations and diffusion scalar maps produced by QSIRecon, computes per-region distribution statistics, builds structural connectivity matrices, and writes analysis-ready outputs in a BIDS-derivative layout.

---

## What QSIParc does

```mermaid
flowchart LR
    A[QSIRecon\nderivatives] --> B[QSIParc]
    B --> C[Diffusion scalar TSV\nlong-format, per-region stats]
    B --> D[Connectivity matrices\nCSV + JSON sidecar × 4 measures]
```

### Scalar extraction

For each atlas region and each diffusion scalar map (FA, MD, ICVF, RD, AD, MAPMRI, DKI, …), QSIParc computes:

| Statistic | Description |
|-----------|-------------|
| `mean` | Arithmetic mean across voxels |
| `median` | Median |
| `std` | Standard deviation |
| `iqr` | Interquartile range |
| `skewness` | Pearson skewness |
| `kurtosis` | Excess kurtosis |
| `n_voxels` | Number of valid (non-NaN) voxels |
| `coverage` | Fraction of atlas-defined voxels with signal |

Results are stacked into a single **long-format TSV** per atlas per session — easy to filter and join in any data analysis tool.

### Structural connectomes

For each tractogram × atlas pair, QSIParc runs `tck2connectome` (MRtrix3) with four standardised measure variants and packages each result as a symmetric N×N CSV plus a JSON sidecar with full provenance.

---

## Quick start

!!! tip "Recommended: Apptainer"
    The Apptainer image is the easiest way to get started — no local Python or MRtrix3 install needed. See the [Installation](installation.md#apptainer-recommended) page for build instructions.

    ```bash
    # Extract all atlases, all subjects
    apptainer run \
        --bind /data/qsirecon:/input:ro \
        --bind /data/qsiparc-out:/output \
        qsiparc.sif /input /output -v

    # Single subject, single atlas
    apptainer run \
        --bind /data/qsirecon:/input:ro \
        --bind /data/qsiparc-out:/output \
        qsiparc.sif /input /output \
        --participant-label sub-001 \
        --atlas Schaefer2018N100Tian2020S2

    # Dry run: see what would be processed
    apptainer run \
        --bind /data/qsirecon:/input:ro \
        --bind /data/qsiparc-out:/output \
        qsiparc.sif /input /output --dry-run
    ```

Alternatively, install directly with pip:

```bash
pip install qsiparc

# Extract all atlases, all subjects
qsiparc /data/qsirecon /data/qsiparc-out -v

# Single subject, single atlas
qsiparc /data/qsirecon /data/qsiparc-out \
    --participant-label sub-001 \
    --atlas Schaefer2018N100Tian2020S2

# Dry run: see what would be processed
qsiparc /data/qsirecon /data/qsiparc-out --dry-run
```

---

## Key design decisions

!!! info "No atlas warping"
    QSIRecon already places atlas parcellations in subject diffusion space.
    QSIParc consumes them directly — no registration step.

!!! info "Direct numpy masking"
    Per-region voxel arrays are extracted with numpy masks rather than nilearn's
    `NiftiLabelsMasker`, giving access to full voxel distributions for all
    higher-order statistics.

!!! info "Long-format output"
    One TSV per atlas per session, all scalars stacked by row. Downstream
    analysis with pandas, R, or any other tool is a single `pd.read_csv` away.

!!! info "Graceful MRtrix3 fallback"
    Scalar extraction works without MRtrix3. Connectome construction is silently
    skipped with a warning if `tck2connectome` is not on `$PATH`.

---

## In scope / out of scope

| In scope | Out of scope |
|----------|-------------|
| Parcellated diffusion scalar maps | FreeSurfer surface metrics (use `fsatlas`) |
| Structural connectivity matrices (4 variants) | Atlas warping/registration |
| QSIRecon built-in atlas set | Tractography reconstruction |
| BIDS-derivative output layout | Any QSIRecon processing step |
| Long-format TSV + JSON sidecar | |

---

## Citation

If you use QSIParc in a publication, please cite it via the repository:
[https://github.com/GalKepler/qsiparc](https://github.com/GalKepler/qsiparc)
