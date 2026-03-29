<p align="center">
  <img src="docs/assets/qsiparc_logo.png" alt="QSIParc logo" width="350">
</p>

<p align="center">
  <a href="https://github.com/GalKepler/qsiparc/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/GalKepler/qsiparc/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://galkepler.github.io/qsiparc/"><img alt="Docs" src="https://img.shields.io/badge/docs-online-blue"></a>
  <a href="https://pypi.org/project/qsiparc/"><img alt="PyPI" src="https://img.shields.io/pypi/v/qsiparc"></a>
  <a href="https://pypi.org/project/qsiparc/"><img alt="Python" src="https://img.shields.io/pypi/pyversions/qsiparc"></a>
  <a href="https://opensource.org/licenses/MIT"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green"></a>
</p>

# QSIParc

Parcellated diffusion feature extraction from [QSIRecon](https://qsirecon.readthedocs.io/) outputs.

QSIParc reads atlas parcellations and diffusion scalar maps produced by QSIRecon, computes per-region distribution statistics using direct numpy masking, and writes analysis-ready TSV files in a BIDS-derivative layout. It also repackages QSIRecon's structural connectivity matrices with standardized JSON sidecar metadata.

Part of the SNBB neuroimaging extraction stack, paired with **fsatlas** (FreeSurfer morphometrics).

## Installation

```bash
pip install -e ".[dev]"
```

## Quick start

```bash
# Extract all atlases, all subjects
qsiparc /data/qsirecon /data/qsiparc-out -v

# Single atlas, single subject
qsiparc /data/qsirecon /data/qsiparc-out \
    --atlas Schaefer2018N100Tian2020S2 \
    --participant-label sub-001 \
    -vv

# Only specific scalars
qsiparc /data/qsirecon /data/qsiparc-out --scalars FA MD ICVF

# Dry run
qsiparc /data/qsirecon /data/qsiparc-out --dry-run
```

## Output layout

```
qsiparc-out/
├── dataset_description.json
└── sub-001/
    └── ses-01/
        └── dwi/
            └── atlas-Schaefer2018N100Tian2020S2/
                ├── sub-001_ses-01_atlas-Schaefer2018N100Tian2020S2_diffmap.tsv
                ├── sub-001_ses-01_atlas-Schaefer2018N100Tian2020S2_desc-streamline_count_connmatrix.csv
                └── sub-001_ses-01_atlas-Schaefer2018N100Tian2020S2_desc-streamline_count_connmatrix.json
```

### Diffusion scalar TSV (long-format)

Each row is one region × one scalar:

| region_index | region_name | hemisphere | scalar | mean | median | std | iqr | skewness | kurtosis | n_voxels | coverage |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | LH_Vis_1 | L | cortex | FA | 0.42 | 0.41 | 0.08 | 0.11 | 0.15 | -0.32 | 847 | 0.98 |

### Connectivity matrix

Square CSV (no headers) + JSON sidecar with region labels, edge weight type, and provenance.

## Architecture

```
qsiparc/
├── discover.py    # BIDS file discovery (globs, entity parsing)
├── atlas.py       # Atlas LUT loading (TSV, JSON, FreeSurfer format)
├── extract.py     # Per-region scalar extraction (numpy masking)
├── connectome.py  # Connectivity matrix passthrough
├── output.py      # BIDS-derivative TSV/JSON writing
└── cli.py         # Click CLI
```

**Key design decisions:**
- Direct numpy masking (not nilearn) for full voxel distribution access
- No atlas warping — consumes QSIRecon's subject-space parcellations
- Long-format TSV with rich statistics (mean, median, std, IQR, skewness, kurtosis)
- Connectome passthrough (repackaging, not recomputation)

## Testing

```bash
pytest
pytest --cov=qsiparc
```

All tests use synthetic 10×10×10 NIfTI volumes — no real data required.

## Contributing

Bug reports, documentation fixes, and pull requests are welcome. See [CONTRIBUTING](https://galkepler.github.io/qsiparc/contributing/) for setup instructions, code style, and guidelines on what is in scope.

## License

MIT
