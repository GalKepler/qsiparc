from pathlib import Path

import pytest

from qsiparc.config import AtlasSelection, load_parcellation_config


def test_load_parcellation_config(tmp_path: Path) -> None:
    config_path = tmp_path / "parcellation.toml"
    atlas_path = tmp_path / "atlas.nii.gz"
    atlas_path.touch()
    config_path.write_text(
        """
[parcellation]
input_root = "/data/qsirecon"
output_root = "/data/qsiparc"
subjects = ["01", "02"]
profile = "volume"

[[parcellation.atlases]]
name = "aal"
path = "{atlas}"
resolution = "2mm"

[parcellation.metrics]
names = ["mean", "median"]
connectivity = true
""".format(
            atlas=atlas_path
        )
    )

    config = load_parcellation_config(config_path)

    assert config.input_root == Path("/data/qsirecon")
    assert config.output_root == Path("/data/qsiparc")
    assert tuple(config.subjects) == ("01", "02")
    assert config.profile == "volume"
    assert config.metrics.names == ("mean", "median")
    assert config.metrics.connectivity is True
    assert config.atlases == [AtlasSelection(name="aal", path=atlas_path, resolution="2mm")]


def test_load_parcellation_config_requires_fields(tmp_path: Path) -> None:
    config_path = tmp_path / "missing.toml"
    config_path.write_text("[parcellation]\nsubjects=[\"01\"]\n")

    with pytest.raises(ValueError):
        load_parcellation_config(config_path)
