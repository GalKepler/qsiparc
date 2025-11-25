# qsiparc

[![Release](https://img.shields.io/github/v/release/GalKepler/qsiparc)](https://img.shields.io/github/v/release/GalKepler/qsiparc)
[![Build status](https://img.shields.io/github/actions/workflow/status/GalKepler/qsiparc/main.yml?branch=main)](https://github.com/GalKepler/qsiparc/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/GalKepler/qsiparc/branch/main/graph/badge.svg)](https://codecov.io/gh/GalKepler/qsiparc)
[![Commit activity](https://img.shields.io/github/commit-activity/m/GalKepler/qsiparc)](https://img.shields.io/github/commit-activity/m/GalKepler/qsiparc)
[![License](https://img.shields.io/github/license/GalKepler/qsiparc)](https://img.shields.io/github/license/GalKepler/qsiparc)

A lightweight Python package for parcellating QSIPrep/QSIRecon diffusion MRI outputs into atlas-level summary tables.

- **Github repository**: <https://github.com/GalKepler/qsiparc/>
- **Documentation** <https://GalKepler.github.io/qsiparc/>

## Current package skeleton

- `qsiparc/config.py`: run configuration objects (subjects, atlases, metrics, profile) with helpers to prepare output roots.
- `qsiparc/io/`: data models plus stubs for discovering QSIRecon outputs and validating inputs.
- `qsiparc/atlas/`: registry for user-provided atlases and transform placeholders.
- `qsiparc/parcellation/`: functional API `parcellate_volume` to compute per-ROI metrics (dict/DataFrame) from an atlas + scalar map, with optional resampling when shapes differ.
- `parcellation.example.toml`: sample settings file for running parcellation over a QSIRecon derivative.
- `notebooks/demo_qsirecon_parcellation.ipynb`: walkthrough to discover recon inputs, plan jobs, and run parcellation (synthetic data included if you don't have a dataset handy).
- `qsiparc/metrics/`: interfaces for region-wise and connectivity metrics.
- `qsiparc/workflows/runner.py`: orchestration stub wiring IO, atlas registry, and provenance tracking.
- `qsiparc/reporting/`: minimal report builder for run notes; will host QC/report outputs.
- `qsiparc/cli.py`: thin CLI wrapper that builds config, preloads user-provided atlases, runs the workflow, and writes a summary.

Atlases are not bundled with the package; point the CLI at paths on disk or those emitted by QSIRecon.

### Next steps

- Flesh out IO discovery for QSIRecon/BIDS derivatives and atlas LUT reading.
- Extend volume parcellation with additional reducers (median, std, counts) and metrics.
- Add richer provenance/logging and integrate report generation with real outputs.

## Getting started with your project

### 1. Create a New Repository

First, create a repository on GitHub with the same name as this project, and then run the following commands:

```bash
git init -b main
git add .
git commit -m "init commit"
git remote add origin git@github.com:GalKepler/qsiparc.git
git push -u origin main
```

### 2. Set Up Your Development Environment

Then, install the environment and the pre-commit hooks with

```bash
make install
```

This will also generate your `uv.lock` file

### 3. Run the pre-commit hooks

Initially, the CI/CD pipeline might be failing due to formatting issues. To resolve those run:

```bash
uv run pre-commit run -a
```

### 4. Commit the changes

Lastly, commit the changes made by the two steps above to your repository.

```bash
git add .
git commit -m 'Fix formatting issues'
git push origin main
```

You are now ready to start development on your project!
The CI/CD pipeline will be triggered when you open a pull request, merge to main, or when you create a new release.

To finalize the set-up for publishing to PyPI, see [here](https://fpgmaas.github.io/cookiecutter-uv/features/publishing/#set-up-for-pypi).
For activating the automatic documentation with MkDocs, see [here](https://fpgmaas.github.io/cookiecutter-uv/features/mkdocs/#enabling-the-documentation-on-github).
To enable the code coverage reports, see [here](https://fpgmaas.github.io/cookiecutter-uv/features/codecov/).

## Releasing a new version

- Create an API Token on [PyPI](https://pypi.org/).
- Add the API Token to your projects secrets with the name `PYPI_TOKEN` by visiting [this page](https://github.com/GalKepler/qsiparc/settings/secrets/actions/new).
- Create a [new release](https://github.com/GalKepler/qsiparc/releases/new) on Github.
- Create a new tag in the form `*.*.*`.

For more details, see [here](https://fpgmaas.github.io/cookiecutter-uv/features/cicd/#how-to-trigger-a-release).

---

Repository initiated with [fpgmaas/cookiecutter-uv](https://github.com/fpgmaas/cookiecutter-uv).
