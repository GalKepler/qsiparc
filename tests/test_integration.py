"""Integration test: full extraction pipeline with synthetic data."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qsiparc.atlas import load_lut_from_tsv
from qsiparc.connectome import load_connectome, write_connectome
from qsiparc.discover import BIDSFile, discover_connectomes, discover_dseg_files, discover_scalar_maps
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

        # 2. Load LUT
        lut = load_lut_from_tsv(bids_tree["lut"], atlas_name="TestAtlas5")

        # 3. Discover and extract scalars
        scalar_files = discover_scalar_maps(qsirecon_dir, "sub-001", "ses-01")
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

        # Verify output structure
        assert tsv_path.exists()
        assert "atlas-TestAtlas5" in str(tsv_path)
        assert tsv_path.suffix == ".tsv"

        # Verify content
        df = pd.read_csv(tsv_path, sep="\t")
        assert len(df) == 10  # 5 regions × 2 scalars
        assert "region_name" in df.columns
        assert "mean" in df.columns
        assert "coverage" in df.columns

        # 5. Connectome passthrough
        conn_files = discover_connectomes(qsirecon_dir, "sub-001", "ses-01")
        assert len(conn_files) == 1

        conn = load_connectome(conn_files[0], lut=lut)
        csv_path, json_path = write_connectome(conn, output_dir, "sub-001", "ses-01")

        assert csv_path.exists()
        assert json_path.exists()

        # Verify connectome sidecar
        with open(json_path) as f:
            sidecar = json.load(f)
        assert sidecar["n_regions"] == 5
        assert sidecar["symmetric"] is True
        assert len(sidecar["region_labels"]) == 5

        # Verify matrix is loadable and correct shape
        matrix = np.loadtxt(csv_path, delimiter=",")
        assert matrix.shape == (5, 5)

        # 6. Dataset description
        desc_path = write_dataset_description(output_dir)
        assert desc_path.exists()
        with open(desc_path) as f:
            desc = json.load(f)
        assert desc["DatasetType"] == "derivative"
