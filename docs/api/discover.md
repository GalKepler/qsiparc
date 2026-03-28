# `qsiparc.discover`

File discovery and BIDS entity parsing. This module is the sole interface between QSIParc and the filesystem — all path assumptions live here.

## Classes

### `BIDSFile`

A discovered file with parsed BIDS entities.

```python
@dataclass(frozen=True)
class BIDSFile:
    path: Path
    entities: dict[str, str]
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `subject` | `str` | Value of the `sub` entity, or `""` |
| `session` | `str` | Value of the `ses` entity, or `""` |
| `atlas` | `str` | Value of the `seg` entity (falls back to `atlas`), or `""` |
| `software` | `str` | QSIRecon workflow name extracted from the path's `qsirecon-*` component |

**Example:**

```python
from qsiparc.discover import BIDSFile
from pathlib import Path

f = BIDSFile(
    path=Path("/data/qsirecon/derivatives/qsirecon-AMICONODDI/sub-001/ses-01/dwi/"
              "sub-001_ses-01_space-ACPC_param-FA_dwimap.nii.gz"),
    entities={"sub": "001", "ses": "01", "space": "ACPC", "param": "FA"},
)

print(f.subject)   # "001"
print(f.software)  # "AMICONODDI"
```

---

### `AtlasDsegFile`

A subject-space atlas dseg NIfTI paired with its atlas LUT.

```python
@dataclass(frozen=True)
class AtlasDsegFile:
    path: Path
    entities: dict[str, str]
    atlas_name: str
    lut_path: Path | None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `subject` | `str` | Value of the `sub` entity |
| `session` | `str` | Value of the `ses` entity |

---

## Functions

### `parse_entities`

```python
def parse_entities(filename: str) -> dict[str, str]
```

Extract BIDS key-value pairs from a filename stem using regex.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `filename` | `str` | Filename (with or without extension) |

**Returns:** `dict[str, str]` — mapping of entity keys to values.

**Example:**

```python
from qsiparc.discover import parse_entities

entities = parse_entities("sub-001_ses-01_space-ACPC_param-FA_dwimap.nii.gz")
# {"sub": "001", "ses": "01", "space": "ACPC", "param": "FA"}
```

---

### `find_atlas_lut`

```python
def find_atlas_lut(qsirecon_dir: Path, atlas_name: str) -> Path | None
```

Find the LUT TSV for a named atlas in the QSIRecon `atlases/` directory.

Looks for: `{qsirecon_dir}/atlases/atlas-{atlas_name}/*_dseg.tsv`

**Returns:** Path to the first matching TSV, or `None` if not found.

---

### `load_lut_for_dseg`

```python
def load_lut_for_dseg(dseg_file: AtlasDsegFile) -> AtlasLUT
```

Load the atlas LUT for a discovered dseg file.

Uses the paired `lut_path` if available; falls back to extracting unique labels from the NIfTI when `lut_path` is `None`.

---

### `discover_dseg_files`

```python
def discover_dseg_files(
    qsirecon_dir: Path,
    participant_label: str | None = None,
    session_label: str | None = None,
    atlas: str | None = None,
) -> list[AtlasDsegFile]
```

Find atlas parcellation NIfTIs in a QSIRecon derivatives directory.

Glob pattern: `{sub_pattern}/{ses_pattern}/dwi/*_dseg.nii.gz`

Files without a `seg-` entity in the filename are skipped.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `qsirecon_dir` | `Path` | Root of the QSIRecon derivatives tree |
| `participant_label` | `str \| None` | Restrict to one subject (e.g. `"sub-001"` or `"001"`) |
| `session_label` | `str \| None` | Restrict to one session (e.g. `"ses-01"` or `"01"`) |
| `atlas` | `str \| None` | Restrict to one atlas name |

**Returns:** `list[AtlasDsegFile]` sorted by path.

---

### `discover_scalar_maps`

```python
def discover_scalar_maps(
    qsirecon_dir: Path,
    subject: str,
    session: str,
    scalars: list[str] | None = None,
) -> list[BIDSFile]
```

Find diffusion scalar map NIfTIs for a given subject/session.

Searches all `derivatives/qsirecon-*` subdirectories for `*_dwimap.nii.gz` files with `space-ACPC`. Files with `_dseg` in the name are skipped.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `qsirecon_dir` | `Path` | Root of the QSIRecon derivatives tree |
| `subject` | `str` | Subject label (with or without `sub-` prefix) |
| `session` | `str` | Session label (with or without `ses-` prefix) |
| `scalars` | `list[str] \| None` | If provided, filter by scalar name (case-insensitive match against `param` entity or filename stem) |

---

### `discover_tractography`

```python
def discover_tractography(
    qsirecon_dir: Path,
    subject: str,
    session: str,
) -> list[BIDSFile]
```

Find tractography files (`*_streamlines.tck.gz`) for a given subject/session.

---

### `discover_sift_weights`

```python
def discover_sift_weights(
    qsirecon_dir: Path,
    subject: str,
    session: str,
) -> list[BIDSFile]
```

Find SIFT2 streamline weight files (`*_streamlineweights.csv`) for a given subject/session.

---

### `sanitize_participant_label` / `sanitize_session_label`

```python
def sanitize_participant_label(participant_label: str) -> str
def sanitize_session_label(session_label: str) -> str
```

Ensure BIDS prefix is present. Idempotent — safe to call on labels with or without the prefix.

```python
sanitize_participant_label("001")      # "sub-001"
sanitize_participant_label("sub-001")  # "sub-001"
sanitize_session_label("01")           # "ses-01"
```
