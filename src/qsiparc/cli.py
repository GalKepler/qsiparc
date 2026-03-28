"""Command-line interface for QSIParc.

Usage:
    qsiparc <qsirecon_dir> <output_dir> [OPTIONS]

Examples:
    # All subjects, all atlases
    qsiparc /data/qsirecon /data/qsiparc-out

    # Single atlas, single subject
    qsiparc /data/qsirecon /data/qsiparc-out \\
        --atlas Schaefer2018N100Tian2020S2 \\
        --participant-label sub-001

    # Specific scalars only
    qsiparc /data/qsirecon /data/qsiparc-out --scalars FA MD ICVF
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from qsiparc.discover import discover_dseg_files, discover_scalar_maps
from qsiparc.atlas import (
    AtlasLUT,
    load_lut_from_dseg,
    load_lut_from_json,
    load_lut_from_tsv,
)
from qsiparc.connectome import load_connectome, write_connectome
from qsiparc.extract import extract_scalar_map, merge_extraction_results
from qsiparc.output import write_dataset_description, write_diffmap_tsv

logger = logging.getLogger("qsiparc")


def _setup_logging(verbosity: int) -> None:
    """Configure logging based on verbosity level."""
    levels = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    level = levels.get(min(verbosity, 2), logging.DEBUG)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)-7s] %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def _find_lut(dseg_path: Path) -> AtlasLUT:
    """Attempt to find and load an atlas LUT adjacent to a dseg file.

    QSIRecon typically places label files alongside the dseg with the same
    stem but a different extension (.tsv, .json, .txt).
    """
    stem = dseg_path.name.replace("_dseg.nii.gz", "")
    parent = dseg_path.parent
    atlas_name = ""
    # Extract atlas name from filename
    for part in stem.split("_"):
        if part.startswith("seg-"):
            atlas_name = part.replace("seg-", "")
            break

    # Try known LUT file patterns
    for suffix, loader in [
        ("_dseg.tsv", load_lut_from_tsv),
        ("_labels.tsv", load_lut_from_tsv),
        ("_dseg.json", load_lut_from_json),
        ("_labels.json", load_lut_from_json),
        ("_dseg.txt", load_lut_from_tsv),
    ]:
        candidate = parent / f"{stem}{suffix}"
        if candidate.exists():
            logger.info("Found LUT file: %s", candidate)
            return loader(candidate, atlas_name=atlas_name)

    # Fallback: extract labels from the dseg itself
    logger.warning("No LUT file found for %s — falling back to dseg labels", dseg_path)
    return load_lut_from_dseg(dseg_path, atlas_name=atlas_name)


@click.command()
@click.argument(
    "qsirecon_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.argument("output_dir", type=click.Path(path_type=Path))
@click.option(
    "--participant-label",
    "-p",
    type=str,
    default=None,
    help="Process a single subject (e.g. sub-001).",
)
@click.option(
    "--session-label",
    "-s",
    type=str,
    default=None,
    help="Process a single session (e.g. ses-01).",
)
@click.option(
    "--atlas",
    "-a",
    type=str,
    default=None,
    help="Process a single atlas (e.g. Schaefer2018N100Tian2020S2).",
)
@click.option(
    "--scalars",
    type=str,
    multiple=True,
    default=None,
    help="Scalar names to extract (default: all discovered). Repeatable.",
)
@click.option(
    "--skip-connectomes",
    is_flag=True,
    default=False,
    help="Skip connectivity matrix extraction.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="List what would be processed without running.",
)
@click.option(
    "-v", "--verbose", count=True, help="Increase verbosity (-v info, -vv debug)."
)
def main(
    qsirecon_dir: Path,
    output_dir: Path,
    participant_label: str | None,
    session_label: str | None,
    atlas: str | None,
    scalars: tuple[str, ...],
    skip_connectomes: bool,
    dry_run: bool,
    verbose: int,
) -> None:
    """Extract parcellated diffusion features from QSIRecon outputs.

    QSIRECON_DIR is the path to QSIRecon derivatives.
    OUTPUT_DIR is where QSIParc outputs will be written.
    """
    _setup_logging(verbose)

    # Discover atlas parcellations
    dseg_files = discover_dseg_files(
        qsirecon_dir,
        participant_label=participant_label,
        session_label=session_label,
        atlas=atlas,
    )

    if not dseg_files:
        logger.error("No dseg files found in %s with given filters.", qsirecon_dir)
        sys.exit(2)

    if dry_run:
        click.echo(f"Found {len(dseg_files)} atlas parcellation(s):")
        for f in dseg_files:
            click.echo(f"  {f.subject}/{f.session} atlas={f.atlas} → {f.path}")
        sys.exit(0)

    # Write dataset description
    write_dataset_description(output_dir)

    n_success = 0
    n_fail = 0

    for dseg_file in dseg_files:
        sub = dseg_file.subject
        ses = dseg_file.session
        atlas_name = dseg_file.atlas
        log_prefix = f"{sub}/{ses}/atlas-{atlas_name}"

        try:
            # Load atlas LUT
            lut = _find_lut(dseg_file.path)

            # --- Scalar extraction ---
            scalar_files = discover_scalar_maps(
                qsirecon_dir,
                subject=f"sub-{sub}",
                session=f"ses-{ses}",
                scalars=list(scalars) if scalars else None,
            )

            results = []
            for sf in scalar_files:
                # Derive scalar name from filename entities
                scalar_name = sf.entities.get(
                    "param", sf.entities.get("desc", sf.path.stem.split("_")[-1])
                )
                try:
                    result = extract_scalar_map(
                        scalar_path=str(sf.path),
                        dseg_path=str(dseg_file.path),
                        lut=lut,
                        scalar_name=scalar_name,
                    )
                    results.append(result)
                except Exception as e:
                    logger.warning(
                        "%s | Failed to extract %s: %s", log_prefix, scalar_name, e
                    )

            if results:
                combined_df = merge_extraction_results(results)
                write_diffmap_tsv(
                    df=combined_df,
                    output_dir=output_dir,
                    subject=f"sub-{sub}",
                    session=f"ses-{ses}",
                    atlas_name=atlas_name,
                )

            # --- Connectome passthrough ---
            if not skip_connectomes:
                ### TODO: Implemet connectome extraction
                pass

            n_success += 1
            logger.info("%s | Done", log_prefix)

        except Exception as e:
            logger.error("%s | Failed: %s", log_prefix, e, exc_info=True)
            n_fail += 1

    # Summary
    click.echo(
        f"\nQSIParc complete: {n_success} succeeded, {n_fail} failed out of {len(dseg_files)} parcellations."
    )

    if n_fail > 0 and n_success == 0:
        sys.exit(2)
    elif n_fail > 0:
        sys.exit(1)
    else:
        sys.exit(0)
