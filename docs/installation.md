# Installation

!!! tip "Recommended: use the Apptainer image"
    For most users — especially on HPC clusters — the Apptainer image is the easiest way to run QSIParc. It bundles Python, MRtrix3, and all dependencies into a single portable file with no local install required. See [Apptainer](#apptainer) below.

## Requirements

- Python ≥ 3.10
- [MRtrix3](https://www.mrtrix.org/) — required for connectome construction only; scalar extraction works without it

## Install from source

```bash
git clone https://github.com/snbb/qsiparc.git
cd qsiparc
pip install -e .
```

## Install with development dependencies

```bash
pip install -e ".[dev]"
```

This adds `pytest`, `ruff`, and `mypy` for testing and linting.

## Verify installation

```bash
qsiparc --help
```

You should see the command-line help output. To also verify MRtrix3 is available for connectome construction:

```bash
which tck2connectome
```

If `tck2connectome` is not on `$PATH`, QSIParc will still run but will skip connectome construction with a warning.

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `nibabel` | ≥ 5.0 | NIfTI file I/O |
| `numpy` | ≥ 1.24 | Array operations and region masking |
| `pandas` | ≥ 2.0 | TSV assembly and data manipulation |
| `scipy` | ≥ 1.10 | Statistical calculations |
| `click` | ≥ 8.0 | CLI framework |
| `parcellate` | ≥ 0.3.1 | Volumetric parcellation wrapper |
| `pybids` | ≥ 0.22.0 | BIDS utilities |

## Docker

A `Dockerfile` is provided to build a portable image bundling Python, MRtrix3, and all dependencies.

```bash
# Build
docker build -t qsiparc .

# Run
docker run --rm \
    -v /data/qsirecon:/input:ro \
    -v /data/output:/output \
    qsiparc /input /output

# With filters
docker run --rm \
    -v /data/qsirecon:/input:ro \
    -v /data/output:/output \
    qsiparc /input /output --participant-label sub-001 --atlas 4S256Parcels
```

## Apptainer (recommended)

An `apptainer.def` definition file is provided to build a portable SIF image bundling Python, MRtrix3, and all dependencies — no local install required. Apptainer is the standard container runtime on most HPC clusters and is the recommended way to run QSIParc.

```bash
# Build the image (requires root or --fakeroot on clusters)
apptainer build qsiparc.sif apptainer.def

# Run
apptainer run \
    --bind /data/qsirecon:/input:ro \
    --bind /data/output:/output \
    qsiparc.sif /input /output

# With filters
apptainer run \
    --bind /data/qsirecon:/input:ro \
    --bind /data/output:/output \
    qsiparc.sif /input /output --participant-label sub-001 --atlas 4S256Parcels
```

Bind your QSIRecon derivatives directory to `/input` and your desired output directory to `/output`. The runscript passes all arguments directly to `qsiparc`.

## MRtrix3

MRtrix3 is an external dependency for connectome construction. Install it following the [official instructions](https://www.mrtrix.org/download/).

In a typical QSIRecon environment (e.g., a Singularity/Docker container), MRtrix3 is already available. QSIParc checks for `tck2connectome` on `$PATH` at startup and warns — but does not fail — if it is absent.

!!! note "Conda environments"
    If you use a conda environment, MRtrix3 can be installed via:
    ```bash
    conda install -c conda-forge mrtrix3
    ```
