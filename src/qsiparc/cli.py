"""Command-line interface for QSIParc.

Usage:
    qsiparc <qsirecon_dir> <output_dir> [OPTIONS]

Examples:
    # All subjects, all atlases
    qsiparc /data/qsirecon /data/qsiparc-out

    # One or more atlases, single subject
    qsiparc /data/qsirecon /data/qsiparc-out \
        --atlas Schaefer2018N100Tian2020S2 \
        --atlas 4S256Parcels \
        --participant-label sub-001

    # Specific scalars only
    qsiparc /data/qsirecon /data/qsiparc-out --scalars FA MD ICVF
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from qsiparc.connectome import build_connectomes, check_mrtrix3
from qsiparc.discover import (
    discover_dseg_files,
    discover_scalar_maps,
    discover_tractography,
    load_lut_for_dseg,
)
from qsiparc.extract import extract_scalar_map
from qsiparc.output import (
    DiffmapProvenance,
    diffmap_tsv_path,
    write_dataset_description,
    write_diffmap_tsv,
)

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


@click.command()
@click.argument(
    "qsirecon_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),  # type: ignore[type-var]
)
@click.argument("output_dir", type=click.Path(path_type=Path))  # type: ignore[type-var]
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
    multiple=True,
    default=None,
    help="Atlas name(s) to process (e.g. Schaefer2018N100Tian2020S2). Repeatable.",
)
@click.option(
    "--scalars",
    type=str,
    multiple=True,
    default=None,
    help="Scalar names to extract (default: all discovered). Repeatable.",
)
@click.option(
    "--stat-tier",
    type=click.Choice(["core", "extended", "diagnostic", "all"], case_sensitive=False),
    default="extended",
    help="Statistic tier for extraction (default: extended).",
)
@click.option(
    "--zero-is-missing",
    is_flag=True,
    default=False,
    help=(
        "Treat zero-valued voxels as missing data during extraction."
        " By default, zeros are included in statistics. Use this flag to"
        " exclude them (e.g. if zero represents no data rather than a true"
        " value)."
    ),
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing outputs (default: skip already-completed outputs).",
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
    atlas: tuple[str, ...],
    scalars: tuple[str, ...],
    stat_tier: str,
    zero_is_missing: bool,
    force: bool,
    dry_run: bool,
    verbose: int,
) -> None:
    """Extract parcellated diffusion features from QSIRecon outputs.

    QSIRECON_DIR is the path to QSIRecon derivatives.
    OUTPUT_DIR is where QSIParc outputs will be written.
    """
    _setup_logging(verbose)

    # Check MRtrix3 availability once at startup.
    mrtrix3_available = check_mrtrix3()
    if not mrtrix3_available:
        logger.warning(
            "tck2connectome not found on PATH — connectome construction will"
            " be skipped. Install MRtrix3 to enable this feature."
        )

    # Discover atlas parcellations
    dseg_files = discover_dseg_files(
        qsirecon_dir,
        participant_label=participant_label,
        session_label=session_label,
        atlas=list(atlas) if atlas else None,
    )

    if not dseg_files:
        logger.error("No dseg files found in %s with given filters.", qsirecon_dir)
        sys.exit(2)

    if dry_run:
        click.echo(f"Found {len(dseg_files)} atlas parcellation(s):")
        for f in dseg_files:
            click.echo(
                f"  {f.subject}/{f.session} atlas={f.atlas_name}"
                f"  lut={'yes' if f.lut_path else 'no'} → {f.path}"
            )
        sys.exit(0)

    # Write dataset description
    write_dataset_description(output_dir)

    n_success = 0
    n_fail = 0

    for dseg_file in dseg_files:
        sub = dseg_file.subject
        ses = dseg_file.session
        atlas_name = dseg_file.atlas_name
        log_prefix = f"sub-{sub}/ses-{ses}/atlas-{atlas_name}"

        try:
            # Load atlas LUT from atlases/ dir (or fall back to dseg labels)
            lut = load_lut_for_dseg(dseg_file)

            # --- Scalar extraction ---
            scalar_files = discover_scalar_maps(
                qsirecon_dir,
                subject=sub,
                session=ses,
                scalars=list(scalars) if scalars else None,
            )

            for sf in scalar_files:
                scalar_name = sf.entities.get(
                    "param", sf.entities.get("desc", sf.path.stem.split("_")[-1])
                )
                try:
                    if not force:
                        expected = diffmap_tsv_path(
                            output_dir=output_dir,
                            subject=f"sub-{sub}",
                            session=f"ses-{ses}",
                            atlas_name=atlas_name,
                            software=sf.software or None,
                            source_entities=sf.entities,
                        )
                        if expected.exists():
                            logger.info(
                                "%s | Skipping existing diffmap TSV: %s",
                                log_prefix,
                                expected.name,
                            )
                            continue
                    result = extract_scalar_map(
                        scalar_path=str(sf.path),
                        dseg_path=str(dseg_file.path),
                        lut=lut,
                        stat_tier=stat_tier,
                        zero_is_missing=zero_is_missing,
                        scalar_name=scalar_name,
                    )
                    provenance = DiffmapProvenance(
                        subject=f"sub-{sub}",
                        session=f"ses-{ses}",
                        atlas_name=atlas_name,
                        atlas_dseg=dseg_file.path,
                        lut_file=dseg_file.lut_path,
                        scalar_name=scalar_name,
                        source_file=sf.path,
                        source_entities=sf.entities,
                        software=sf.software or None,
                    )
                    write_diffmap_tsv(
                        df=result.stats_df,
                        output_dir=output_dir,
                        subject=f"sub-{sub}",
                        session=f"ses-{ses}",
                        atlas_name=atlas_name,
                        provenance=provenance,
                        force=force,
                    )
                except Exception as e:
                    logger.warning(
                        "%s | Failed to extract %s: %s", log_prefix, scalar_name, e
                    )

            # --- Connectome construction ---
            if mrtrix3_available:
                tck_files = discover_tractography(
                    qsirecon_dir, subject=sub, session=ses
                )
                if not tck_files:
                    logger.debug(
                        "%s | No tractography files found — skipping connectomes",
                        log_prefix,
                    )
                for tck_file in tck_files:
                    try:
                        build_connectomes(
                            tck_file=tck_file,
                            dseg_file=dseg_file,
                            lut=lut,
                            output_dir=output_dir,
                            subject=f"sub-{sub}",
                            session=f"ses-{ses}",
                            force=force,
                        )
                    except Exception as e:
                        logger.error(
                            "%s | Connectome failed for %s: %s",
                            log_prefix,
                            tck_file.path.name,
                            e,
                        )

            n_success += 1
            logger.info("%s | Done", log_prefix)

        except Exception as e:
            logger.error("%s | Failed: %s", log_prefix, e, exc_info=True)
            n_fail += 1

    # Summary
    click.echo(
        f"\nQSIParc complete: {n_success} succeeded, {n_fail} failed"
        f" out of {len(dseg_files)} parcellations."
    )

    if n_fail > 0 and n_success == 0:
        sys.exit(2)
    elif n_fail > 0:
        sys.exit(1)
    else:
        sys.exit(0)
