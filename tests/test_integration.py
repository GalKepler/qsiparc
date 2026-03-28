"""Integration test: full extraction pipeline with synthetic data."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qsiparc.connectome import load_connectome, write_connectome
from qsiparc.discover import BIDSFile, discover_dseg_files, discover_scalar_maps, load_lut_for_dseg
from qsiparc.extract import extract_scalar_map, merge_extraction_results
from qsiparc.output import write_dataset_description, write_diffmap_tsv


class TestFullPipeline:
    """End-to-end test mirroring what the CLI does."""

    def test_pipeline(self, bids_tree, tmp_path):
        output_dir = tmp_path / "qsiparc-out"
        qsirecon_dir = bids_tree["root"]

        # 1. Discover dseg
        dsegs = discover_dseg_files(qsirecon_dir)
        assert len(dsegs) == 1
        dseg = dsegs[0]
        assert dseg.atlas_name == "TestAtlas5"
        assert dseg.lut_path is not None

        # 2. Load LUT from atlases/ directory
        lut = load_lut_for_dseg(dseg)
        assert len(lut) == 5
        assert lut[1].name == "LH_Vis_1"

        # 3. Discover and extract scalars
        scalar_files = discover_scalar_maps(qsirecon_dir, "sub-001", "ses-01")
        assert len(scalar_files) == 2

        results = []
        for sf in scalar_files:
            scalar_name = sf.entities.get("param", "unknown")
            result = extract_scalar_map(
                scalar_path=str(sf.path),
                dseg_path=str(dseg.path),
                lut=lut,
                scalar_name=scalar_name,
            )
            results.append(result)

        assert len(results) == 2  # FA + MD

        # 4. Merge and write
        combined = merge_extraction_results(results)
        tsv_path = write_diffmap_tsv(combined, output_dir, "sub-001", "ses-01", "TestAtlas5")

        assert tsv_path.exists()
        assert "atlas-TestAtlas5" in str(tsv_path)
        assert tsv_path.suffix == ".tsv"

        df = pd.read_csv(tsv_path, sep="\t")
        assert len(df) == 10  # 5 regions × 2 scalars
        assert "region_name" in df.columns
        assert "mean" in df.columns
        assert "coverage" in df.columns

        # 5. Connectome passthrough (load from known path, no discovery needed)
        conn_file = BIDSFile(path=bids_tree["connectome"], entities={})
        conn = load_connectome(conn_file, lut=lut)
        csv_path, json_path = write_connectome(conn, output_dir, "sub-001", "ses-01")

        assert csv_path.exists()
        assert json_path.exists()

        with open(json_path) as f:
            sidecar = json.load(f)
        assert sidecar["n_regions"] == 5
        assert sidecar["symmetric"] is True
        assert len(sidecar["region_labels"]) == 5

        matrix = np.loadtxt(csv_path, delimiter=",")
        assert matrix.shape == (5, 5)

        # 6. Dataset description
        desc_path = write_dataset_description(output_dir)
        assert desc_path.exists()
        with open(desc_path) as f:
            desc = json.load(f)
        assert desc["DatasetType"] == "derivative"
