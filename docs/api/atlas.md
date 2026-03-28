# `qsiparc.atlas`

Atlas look-up table (LUT) loading and region metadata. Provides a unified interface for loading atlas label files regardless of format.

## Classes

### `RegionInfo`

Immutable metadata for a single atlas region.

```python
@dataclass(frozen=True)
class RegionInfo:
    index: int          # Integer label in the dseg NIfTI
    name: str           # Human-readable region name
    hemisphere: str     # "L", "R", or "bilateral"
```

---

### `AtlasLUT`

Container for an ordered list of `RegionInfo` objects. Supports index-based lookup.

```python
class AtlasLUT:
    regions: list[RegionInfo]
    atlas_name: str
```

**Constructor:**

```python
AtlasLUT(regions: list[RegionInfo], atlas_name: str = "")
```

**Methods:**

| Method | Returns | Description |
|--------|---------|-------------|
| `__len__()` | `int` | Number of regions |
| `__getitem__(index)` | `RegionInfo` | Look up by integer label |
| `get(index, default=None)` | `RegionInfo \| None` | Safe lookup |
| `to_dataframe()` | `pd.DataFrame` | DataFrame with `region_index`, `region_name`, `hemisphere` columns |

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `indices` | `list[int]` | Sorted list of all region integer labels |

**Example:**

```python
from qsiparc.atlas import AtlasLUT, RegionInfo

lut = AtlasLUT(
    regions=[
        RegionInfo(index=1, name="LH_Vis_1", hemisphere="L"),
        RegionInfo(index=2, name="RH_Vis_1", hemisphere="R"),
    ],
    atlas_name="Schaefer2018N100Tian2020S2",
)

print(len(lut))         # 2
print(lut[1].name)      # "LH_Vis_1"
print(lut.indices)      # [1, 2]
```

---

## Functions

### `infer_hemisphere`

```python
def infer_hemisphere(name: str) -> str
```

Guess hemisphere from a region name string. Returns `"L"`, `"R"`, or `"bilateral"`.

Recognized patterns:

| Pattern type | Left (`L`) | Right (`R`) |
|-------------|-----------|------------|
| Prefix | `lh_`, `lh-`, `lh.`, `left_`, `left-`, `l_` | `rh_`, `rh-`, `rh.`, `right_`, `right-`, `r_` |
| Suffix | `_lh`, `-lh`, `_left`, `-left`, `_l` | `_rh`, `-rh`, `_right`, `-right`, `_r` |
| Infix | `_lh_`, `_LH_` | `_rh_`, `_RH_` |
| Schaefer-style | `7Networks_LH_Vis_1` | `7Networks_RH_Vis_1` |

**Example:**

```python
from qsiparc.atlas import infer_hemisphere

infer_hemisphere("LH_Vis_1")             # "L"
infer_hemisphere("7Networks_RH_Vis_1")   # "R"
infer_hemisphere("Thalamus-Left")        # "L"
infer_hemisphere("Brain-Stem")           # "bilateral"
```

---

### `load_lut_from_tsv`

```python
def load_lut_from_tsv(path: Path, atlas_name: str = "") -> AtlasLUT
```

Load a TSV LUT file. Auto-detects index and name columns by name. Falls back to FreeSurfer-style LUT parsing if pandas fails.

Expected columns (case-insensitive):

| Column role | Accepted names |
|-------------|---------------|
| Index | `index`, `id`, `region_id` |
| Name | `name`, `label`, `region`, `label_name`, `region_name` |
| Hemisphere | `hemisphere` (optional; inferred if absent) |

Background label (index = 0) is automatically skipped.

---

### `load_lut_from_json`

```python
def load_lut_from_json(path: Path, atlas_name: str = "") -> AtlasLUT
```

Load a JSON LUT file. Accepts two formats:

```json
{"1": "RegionName", "2": "RegionName"}
```

or:

```json
[{"index": 1, "name": "RegionName", "hemisphere": "L"}, ...]
```

---

### `load_lut_from_dseg`

```python
def load_lut_from_dseg(dseg_path: Path, atlas_name: str = "") -> AtlasLUT
```

Fallback: extract unique non-zero integer labels from a dseg NIfTI and assign generic names (`region_0001`, `region_0002`, …). All regions get `hemisphere = "bilateral"`.

!!! warning
    Only use this when no proper LUT file is available. Generic region names are not useful for downstream analysis.
