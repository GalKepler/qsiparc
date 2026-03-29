# Contributing

Contributions are welcome — bug reports, documentation improvements, and pull requests all help.

## Getting started

Fork and clone the repository, then install in editable mode with dev dependencies:

```bash
git clone https://github.com/GalKepler/qsiparc.git
cd qsiparc
pip install -e ".[dev]"
```

## Running the test suite

```bash
pytest
pytest --cov=qsiparc   # with coverage
```

All tests use synthetic 10×10×10 NIfTI volumes — no real QSIRecon data required. Tests that exercise MRtrix3 integration are automatically skipped when `tck2connectome` is not on `$PATH`.

## Code style

QSIParc uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting, and [mypy](https://mypy.readthedocs.io/) for type checking.

```bash
ruff check src tests   # lint
ruff format src tests  # format
mypy src/qsiparc       # type check
```

These checks run in CI on every push and pull request.

## Submitting a pull request

1. Create a branch from `main` with a descriptive name (`fix/discovery-glob`, `feat/add-afd-scalar`, etc.).
2. Make your changes, add or update tests as needed.
3. Ensure `pytest`, `ruff check`, and `mypy` all pass locally.
4. Open a pull request against `main` and describe what changed and why.

## Reporting bugs

Please open an [issue on GitHub](https://github.com/GalKepler/qsiparc/issues) with:

- QSIParc version (`qsiparc --version`)
- Python and MRtrix3 versions
- A minimal reproduction (command, input layout, error message / traceback)

## Out-of-scope contributions

QSIParc is intentionally narrow. The following are out of scope and pull requests for them will not be merged:

- Atlas warping or registration logic
- FreeSurfer surface metric extraction (see `fsatlas`)
- Reimplementing `tck2connectome` in Python
- Support for non-QSIRecon input layouts

If you are unsure whether a contribution fits, open an issue to discuss before writing code.

## License

By contributing you agree that your work will be released under the [MIT License](https://github.com/GalKepler/qsiparc/blob/main/LICENSE).
