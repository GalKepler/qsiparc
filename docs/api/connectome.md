# `qsiparc.connectome`

Structural connectivity matrix construction via MRtrix3's `tck2connectome`.

## Constants

### `MEASURES`

```python
MEASURES: dict[str, dict] = {
    "sift_invnodevol_radius2_count": {
        "flags": ["-assignment_radial_search", "2", "-scale_invnodevol",
                  "-symmetric", "-stat_edge", "sum"],
        "needs_sift_weights": True,
    },
    "radius2_meanlength": {
        "flags": ["-assignment_radial_search", "2", "-scale_length",
                  "-symmetric", "-stat_edge", "mean"],
        "needs_sift_weights": False,
    },
    "radius2_count": {
        "flags": ["-assignment_radial_search", "2",
                  "-symmetric", "-stat_edge", "sum"],
        "needs_sift_weights": False,
    },
    "sift_radius2_count": {
        "flags": ["-assignment_radial_search", "2",
                  "-symmetric", "-stat_edge", "sum"],
        "needs_sift_weights": True,
    },
}
```

The four standardised connectivity measures. Keys are used as the `desc-` BIDS entity in output filenames.

## Classes

### `ConnectomeResult`

A computed connectivity matrix with full provenance metadata.

```python
@dataclass
class ConnectomeResult:
    matrix: np.ndarray          # shape (N, N)
    atlas_name: str
    measure: str                # e.g. "sift_invnodevol_radius2_count"
    region_labels: list[str]    # region names in matrix row/column order
    csv_path: Path
    json_path: Path
    tck_path: Path
    dseg_path: Path
    sift_weights_path: Path | None
    cmd: list[str]              # exact tck2connectome command that was run
```

## Functions

### `check_mrtrix3`

```python
def check_mrtrix3() -> bool
```

Return `True` if `tck2connectome` is reachable on `$PATH`. Uses `shutil.which` — no subprocess is invoked.

```python
from qsiparc.connectome import check_mrtrix3

if not check_mrtrix3():
    print("MRtrix3 not found — connectomes will be skipped")
```

---

### `find_sift_weights_for_tck`

```python
def find_sift_weights_for_tck(tck_path: Path) -> Path | None
```

Find the SIFT2 weight file adjacent to a tractography file.

Searches the same directory for:
1. `*_streamlineweights.csv`
2. `*_siftweights.csv`

Returns the first match, or `None`.

---

### `build_tck2connectome_cmd`

```python
def build_tck2connectome_cmd(
    tck_path: Path,
    dseg_path: Path,
    out_csv: Path,
    measure: str,
    sift_weights: Path | None = None,
) -> list[str]
```

Assemble the `tck2connectome` argv list for a given measure without running it.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `tck_path` | `Path` | Input tractogram (plain `.tck`, not `.tck.gz`) |
| `dseg_path` | `Path` | Atlas parcellation as node image |
| `out_csv` | `Path` | Output CSV path |
| `measure` | `str` | One of the keys in `MEASURES` |
| `sift_weights` | `Path \| None` | SIFT2 weight file (required when `MEASURES[measure]["needs_sift_weights"]`) |

**Raises:**

| Exception | Condition |
|-----------|-----------|
| `ValueError` | Unknown measure name |
| `ValueError` | SIFT2 weights required but not provided |

**Example:**

```python
from pathlib import Path
from qsiparc.connectome import build_tck2connectome_cmd

cmd = build_tck2connectome_cmd(
    tck_path=Path("/tmp/streamlines.tck"),
    dseg_path=Path("/data/atlas.nii.gz"),
    out_csv=Path("/out/connectome.csv"),
    measure="radius2_count",
)
# ["tck2connectome", "/tmp/streamlines.tck", "/data/atlas.nii.gz",
#  "/out/connectome.csv", "-assignment_radial_search", "2",
#  "-symmetric", "-stat_edge", "sum"]
```

This function is used in unit tests to verify correct flag assembly without invoking MRtrix3.

---

### `build_connectomes`

```python
def build_connectomes(
    tck_file: BIDSFile,
    dseg_file: AtlasDsegFile,
    lut: AtlasLUT,
    output_dir: Path,
    subject: str,
    session: str,
) -> list[ConnectomeResult]
```

Run all four `tck2connectome` measures for one tractogram × atlas pair.

**Behaviour:**

- Decompresses `.tck.gz` to a temporary `.tck` (MRtrix3 requirement), runs all measures, then deletes the temporary file.
- Skips measures requiring SIFT2 weights when none are found adjacent to the tractogram.
- Raises `subprocess.CalledProcessError` on non-zero `tck2connectome` exit (caller handles per-subject errors).
- Writes CSV + JSON sidecar for each completed measure.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `tck_file` | `BIDSFile` | Discovered tractography file |
| `dseg_file` | `AtlasDsegFile` | Atlas parcellation in subject space |
| `lut` | `AtlasLUT` | Atlas LUT for region labels in JSON sidecar |
| `output_dir` | `Path` | Root output directory |
| `subject` | `str` | Subject label with prefix (e.g. `"sub-001"`) |
| `session` | `str` | Session label with prefix (e.g. `"ses-01"`) |

**Returns:** `list[ConnectomeResult]` — one entry per successfully completed measure.

**Raises:** `subprocess.CalledProcessError` if any `tck2connectome` call exits non-zero.
