# CLI Reference

QSIParc exposes a single command: `qsiparc`.

## Synopsis

```
qsiparc [OPTIONS] QSIRECON_DIR OUTPUT_DIR
```

## Arguments

| Argument | Description |
|----------|-------------|
| `QSIRECON_DIR` | Path to the QSIRecon derivatives directory. Must exist. |
| `OUTPUT_DIR` | Path to write QSIParc outputs. Created if it does not exist. |

## Options

### Filtering

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--participant-label` | `-p` | `str` | all subjects | Process a single subject. Accepts `sub-001` or `001`. |
| `--session-label` | `-s` | `str` | all sessions | Process a single session. Accepts `ses-01` or `01`. |
| `--atlas` | `-a` | `str` | all atlases | Process a single atlas by name (e.g. `Schaefer2018N100Tian2020S2`). |
| `--scalars` | | `str` (repeatable) | all discovered | Scalar names to extract. Repeatable: `--scalars FA --scalars MD`. |

### Processing

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--stat-tier` | choice | `extended` | Statistic tier. One of `core`, `extended`, `diagnostic`, `all`. |
| `--zero-is-missing` | flag | off | Treat voxels with value `0.0` as missing data (NaN) during extraction. Useful for masked diffusion maps where background = 0. |

### Execution

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--dry-run` | | flag | off | List what would be processed without actually running. |
| `--verbose` | `-v` | count | 0 (WARNING) | Increase verbosity. `-v` → INFO, `-vv` → DEBUG. |

## Examples

```bash
# All subjects, all atlases, default settings
qsiparc /data/qsirecon /data/qsiparc-out

# Single subject with INFO logging
qsiparc /data/qsirecon /data/qsiparc-out \
    --participant-label sub-001 \
    -v

# Single subject, single session, debug logging
qsiparc /data/qsirecon /data/qsiparc-out \
    --participant-label sub-001 \
    --session-label ses-01 \
    -vv

# Single atlas only
qsiparc /data/qsirecon /data/qsiparc-out \
    --atlas Schaefer2018N100Tian2020S2

# Only specific scalar maps
qsiparc /data/qsirecon /data/qsiparc-out \
    --scalars FA \
    --scalars MD \
    --scalars ICVF

# Treat zeros as missing data (common for masked diffusion maps)
qsiparc /data/qsirecon /data/qsiparc-out --zero-is-missing

# Dry run: see what would be processed
qsiparc /data/qsirecon /data/qsiparc-out --dry-run
```

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | All parcellations succeeded |
| `1` | Partial failure — some subjects/atlases failed, others succeeded |
| `2` | Total failure — no successful outputs |

## Logging format

```
HH:MM:SS [LEVEL  ] module | message
```

Each log message includes the module name for easy filtering. At INFO level, every extracted scalar and written file is logged. At DEBUG level, full subprocess commands are printed.

## Stat tiers

The `--stat-tier` option controls which columns appear in the output TSV:

| Tier | Columns included |
|------|-----------------|
| `core` | `mean` |
| `extended` | `mean`, `median`, `std`, `iqr`, `skewness`, `kurtosis`, `n_voxels`, `coverage` |
| `diagnostic` | All extended + additional diagnostic metrics |
| `all` | Everything available |

The default `extended` tier provides the full set described in the [Output Format](outputs.md) specification.
