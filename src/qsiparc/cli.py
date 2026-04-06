"""Command-line interface for QSIParc.

Commands:
    run        Extract parcellated diffusion features from QSIRecon outputs.
    aggregate  Collect per-subject QSIParc outputs into group-level tables.

Examples (run):
    # All subjects, all atlases
    qsiparc run /data/qsirecon /data/qsiparc-out

    # One or more atlases, single subject
    qsiparc run /data/qsirecon /data/qsiparc-out \\
        --atlas Schaefer2018N100Tian2020S2 \\
        --atlas 4S256Parcels \\
        --participant-label sub-001

    # Specific scalars only
    qsiparc run /data/qsirecon /data/qsiparc-out --scalars FA MD ICVF

    # Run with 8 parallel workers
    qsiparc run /data/qsirecon /data/qsiparc-out --n-procs 8

    # Use all available CPUs
    qsiparc run /data/qsirecon /data/qsiparc-out --n-procs -1

Examples (aggregate):
    # Aggregate all atlases
    qsiparc aggregate /data/qsiparc-out

    # Aggregate a specific atlas, diffmaps only
    qsiparc aggregate /data/qsiparc-out --atlas Schaefer2018N100Tian2020S2 \
        --data-type diffmap
"""

from __future__ import annotations

import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import click

from qsiparc.aggregate import (
    _atlas_from_key,
    aggregate_connectomes,
    aggregate_diffmaps,
    discover_connmatrix_csvs,
    discover_diffmap_tsvs,
    write_aggregate_tsv,
)
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
    """Configure logging based on verbosity level.

    0 (default) → INFO: progress messages visible without any flags
    -v          → INFO with file-level logger names shown
    -vv         → DEBUG: full detail including internal library messages
    """
    level = logging.DEBUG if verbosity >= 2 else logging.INFO
    fmt = (
        "%(asctime)s [%(levelname)-7s] %(name)s | %(message)s"
        if verbosity >= 1
        else "%(asctime)s [%(levelname)-7s] %(message)s"
    )
    logging.basicConfig(level=level, format=fmt, datefmt="%H:%M:%S")
    # Suppress noisy third-party loggers unless the user asked for full debug.
    if verbosity < 2:
        for noisy in ("nibabel", "matplotlib", "PIL", "numexpr"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


def _process_dseg(
    dseg_file: Path,
    qsirecon_dir: Path,
    output_dir: Path,
    scalars: tuple[str, ...],
    stat_tier: str,
    zero_is_missing: bool,
    force: bool,
    mrtrix3_available: bool,
    verbosity: int,
) -> tuple[bool, str | None]:
    """Process a single atlas dseg file: scalar extraction + connectome construction.

    Returns (success, error_message). This is a top-level function so it can be
    pickled by ProcessPoolExecutor.
    """
    _setup_logging(verbosity)
    _logger = logging.getLogger("qsiparc")

    sub = dseg_file.subject
    ses = dseg_file.session
    atlas_name = dseg_file.atlas_name
    log_prefix = f"sub-{sub}/ses-{ses}/atlas-{atlas_name}"

    try:
        _logger.info("==> Starting %s", log_prefix)
        _logger.info(
            "%s | Loading atlas LUT from: %s",
            log_prefix,
            dseg_file.lut_path or "dseg fallback",
        )
        lut = load_lut_for_dseg(dseg_file)
        _logger.info("%s | Atlas has %d regions", log_prefix, len(lut.regions))

        # --- Scalar extraction ---
        _logger.info("%s | Discovering scalar maps...", log_prefix)
        scalar_files = discover_scalar_maps(
            qsirecon_dir,
            subject=sub,
            session=ses,
            scalars=list(scalars) if scalars else None,
        )
        _logger.info("%s | Found %d scalar map(s)", log_prefix, len(scalar_files))

        for sf_idx, sf in enumerate(scalar_files, 1):
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
                        _logger.info(
                            "%s | [%d/%d] Skipping %s — output already exists",
                            log_prefix,
                            sf_idx,
                            len(scalar_files),
                            scalar_name,
                        )
                        continue
                _logger.info(
                    "%s | [%d/%d] Extracting scalar: %s",
                    log_prefix,
                    sf_idx,
                    len(scalar_files),
                    scalar_name,
                )
                _logger.info("%s |         source: %s", log_prefix, sf.path.name)
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
                tsv_path = write_diffmap_tsv(
                    df=result.stats_df,
                    output_dir=output_dir,
                    subject=f"sub-{sub}",
                    session=f"ses-{ses}",
                    atlas_name=atlas_name,
                    provenance=provenance,
                    force=force,
                )
                _logger.info(
                    "%s | [%d/%d] Wrote diffmap TSV (%d rows): %s",
                    log_prefix,
                    sf_idx,
                    len(scalar_files),
                    len(result.stats_df),
                    tsv_path.name if tsv_path else "?",
                )
            except Exception as e:
                _logger.warning(
                    "%s | Failed to extract %s: %s", log_prefix, scalar_name, e
                )

        # --- Connectome construction ---
        if mrtrix3_available:
            _logger.info("%s | Discovering tractography files...", log_prefix)
            tck_files = discover_tractography(qsirecon_dir, subject=sub, session=ses)
            if not tck_files:
                _logger.info(
                    "%s | No tractography files found — skipping connectomes",
                    log_prefix,
                )
            else:
                _logger.info("%s | Found %d tractogram(s)", log_prefix, len(tck_files))
            for tck_idx, tck_file in enumerate(tck_files, 1):
                _logger.info(
                    "%s | [%d/%d] Building connectomes for: %s",
                    log_prefix,
                    tck_idx,
                    len(tck_files),
                    tck_file.path.name,
                )
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
                    _logger.error(
                        "%s | Connectome failed for %s: %s",
                        log_prefix,
                        tck_file.path.name,
                        e,
                    )

        _logger.info("==> Finished %s", log_prefix)
        return True, None

    except Exception as e:
        logging.getLogger("qsiparc").error(
            "%s | Failed: %s", log_prefix, e, exc_info=True
        )
        return False, str(e)


@click.group()
def main() -> None:
    """QSIParc — parcellated diffusion feature extraction from QSIRecon outputs.

    Use ``qsiparc run`` to extract features, and ``qsiparc aggregate`` to
    collect per-subject outputs into group-level tables.
    """


@main.command("run")
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
    "--n-procs",
    "-n",
    type=int,
    default=1,
    show_default=True,
    help=(
        "Number of parallel worker processes. Each worker handles one"
        " subject/session/atlas combination. Use -1 to use all available CPUs."
    ),
)
@click.option(
    "-v", "--verbose", count=True, help="Increase verbosity (-v info, -vv debug)."
)
def run(
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
    n_procs: int,
    verbose: int,
) -> None:
    """Extract parcellated diffusion features from QSIRecon outputs.

    QSIRECON_DIR is the path to QSIRecon derivatives.
    OUTPUT_DIR is where QSIParc outputs will be written.
    """
    _setup_logging(verbose)

    logger.info("QSIParc starting up")
    logger.info("  Input (QSIRecon):  %s", qsirecon_dir)
    logger.info("  Output directory:  %s", output_dir)

    # Resolve -1 → all CPUs
    n_workers = os.cpu_count() if n_procs == -1 else n_procs
    if n_workers < 1:
        logger.error("--n-procs must be >= 1 or -1 (all CPUs), got %d", n_procs)
        sys.exit(2)

    logger.info("  Workers:           %d", n_workers)
    logger.info("  Stat tier:         %s", stat_tier)
    if scalars:
        logger.info("  Scalar filter:     %s", ", ".join(scalars))
    if atlas:
        logger.info("  Atlas filter:      %s", ", ".join(atlas))
    if participant_label:
        logger.info("  Subject filter:    %s", participant_label)
    if session_label:
        logger.info("  Session filter:    %s", session_label)
    if force:
        logger.info("  Force overwrite:   yes")
    if zero_is_missing:
        logger.info("  Zero-is-missing:   yes")

    # Check MRtrix3 availability once at startup.
    mrtrix3_available = check_mrtrix3()
    if mrtrix3_available:
        logger.info("  MRtrix3:           found (connectomes enabled)")
    else:
        logger.warning(
            "tck2connectome not found on PATH — connectome construction will"
            " be skipped. Install MRtrix3 to enable this feature."
        )

    # Discover atlas parcellations
    logger.info("Discovering atlas parcellations in %s ...", qsirecon_dir)
    dseg_files = discover_dseg_files(
        qsirecon_dir,
        participant_label=participant_label,
        session_label=session_label,
        atlas=list(atlas) if atlas else None,
    )

    if not dseg_files:
        logger.error("No dseg files found in %s with given filters.", qsirecon_dir)
        sys.exit(2)

    logger.info(
        "Found %d parcellation(s) to process across %d unique subject/session pair(s).",
        len(dseg_files),
        len({(f.subject, f.session) for f in dseg_files}),
    )

    if dry_run:
        click.echo(f"Found {len(dseg_files)} atlas parcellation(s):")
        for f in dseg_files:
            click.echo(
                f"  {f.subject}/{f.session} atlas={f.atlas_name}"
                f"  lut={'yes' if f.lut_path else 'no'} → {f.path}"
            )
        sys.exit(0)

    # Write dataset description once before spawning workers.
    write_dataset_description(output_dir)

    if n_workers > 1:
        logger.info(
            "Running with %d parallel worker(s) across %d parcellation(s).",
            n_workers,
            len(dseg_files),
        )

    # Build a partial-like call signature shared across all workers.
    common_kwargs = dict(
        qsirecon_dir=qsirecon_dir,
        output_dir=output_dir,
        scalars=scalars,
        stat_tier=stat_tier,
        zero_is_missing=zero_is_missing,
        force=force,
        mrtrix3_available=mrtrix3_available,
        verbosity=verbose,
    )

    results: list[tuple[bool, str | None]] = []

    if n_workers == 1:
        for idx, dseg_file in enumerate(dseg_files, 1):
            logger.info(
                "--- [%d/%d] sub-%s / ses-%s / atlas-%s ---",
                idx,
                len(dseg_files),
                dseg_file.subject,
                dseg_file.session,
                dseg_file.atlas_name,
            )
            results.append(_process_dseg(dseg_file, **common_kwargs))
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            future_to_dseg = {
                executor.submit(_process_dseg, dseg_file, **common_kwargs): dseg_file
                for dseg_file in dseg_files
            }
            for future in as_completed(future_to_dseg):
                dseg_file = future_to_dseg[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.error(
                        "sub-%s/ses-%s/atlas-%s | Worker crashed: %s",
                        dseg_file.subject,
                        dseg_file.session,
                        dseg_file.atlas_name,
                        e,
                    )
                    results.append((False, str(e)))

    n_success = sum(1 for ok, _ in results if ok)
    n_fail = len(results) - n_success

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


@main.command("aggregate")
@click.argument(
    "qsiparc_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),  # type: ignore[type-var]
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),  # type: ignore[type-var]
    default=None,
    help=("Directory to write aggregate tables (default: <qsiparc_dir>/group)."),
)
@click.option(
    "--atlas",
    "-a",
    type=str,
    multiple=True,
    default=None,
    help="Atlas name(s) to aggregate (default: all). Repeatable.",
)
@click.option(
    "--data-type",
    "-d",
    type=click.Choice(["diffmap", "connmatrix", "all"], case_sensitive=False),
    default="all",
    show_default=True,
    help="Which data type(s) to aggregate.",
)
@click.option(
    "--include-diagonal",
    is_flag=True,
    default=False,
    help="Include self-connections (diagonal) in connectome edge lists.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing aggregate files.",
)
@click.option(
    "-v", "--verbose", count=True, help="Increase verbosity (-v info, -vv debug)."
)
def aggregate(
    qsiparc_dir: Path,
    output_dir: Path | None,
    atlas: tuple[str, ...],
    data_type: str,
    include_diagonal: bool,
    force: bool,
    verbose: int,
) -> None:
    """Aggregate per-subject QSIParc outputs into group-level tables.

    QSIPARC_DIR is the output directory from a previous ``qsiparc run``
    invocation.  Aggregate TSVs are written to <QSIPARC_DIR>/group/ by
    default (one file per atlas per data type).
    """
    _setup_logging(verbose)

    effective_output_dir = (
        output_dir if output_dir is not None else qsiparc_dir / "group"
    )
    atlas_filter = list(atlas) if atlas else None

    logger.info("QSIParc aggregate starting")
    logger.info("  Input (QSIParc):   %s", qsiparc_dir)
    logger.info("  Output directory:  %s", effective_output_dir)
    if atlas_filter:
        logger.info("  Atlas filter:      %s", ", ".join(atlas_filter))
    logger.info("  Data type:         %s", data_type)

    n_written = 0
    any_found = False

    # --- Diffmap aggregation ---
    if data_type in ("diffmap", "all"):
        diffmap_files = discover_diffmap_tsvs(qsiparc_dir, atlas=atlas_filter)
        if diffmap_files:
            any_found = True
            logger.info("Found %d diffmap TSV(s) to aggregate.", len(diffmap_files))
            grouped = aggregate_diffmaps(diffmap_files)
            for key, df in grouped.items():
                atlas_name = _atlas_from_key(key)
                out_path = (
                    effective_output_dir / "dwi" / f"atlas-{atlas_name}" / f"{key}.tsv"
                )
                if out_path.exists() and not force:
                    logger.info(
                        "atlas-%s | Skipping %s — already exists",
                        atlas_name,
                        out_path.name,
                    )
                    continue
                write_aggregate_tsv(df, out_path)
                logger.info(
                    "atlas-%s | Wrote diffmap aggregate (%d rows): %s",
                    atlas_name,
                    len(df),
                    out_path,
                )
                n_written += 1
        else:
            logger.info("No diffmap TSVs found.")

    # --- Connectome aggregation ---
    if data_type in ("connmatrix", "all"):
        connmatrix_files = discover_connmatrix_csvs(qsiparc_dir, atlas=atlas_filter)
        if connmatrix_files:
            any_found = True
            logger.info(
                "Found %d connmatrix CSV(s) to aggregate.", len(connmatrix_files)
            )
            grouped_conn = aggregate_connectomes(
                connmatrix_files, include_diagonal=include_diagonal
            )
            for key, df in grouped_conn.items():
                atlas_name = _atlas_from_key(key)
                out_path = (
                    effective_output_dir / "dwi" / f"atlas-{atlas_name}" / f"{key}.tsv"
                )
                if out_path.exists() and not force:
                    logger.info(
                        "atlas-%s | Skipping %s — already exists",
                        atlas_name,
                        out_path.name,
                    )
                    continue
                write_aggregate_tsv(df, out_path)
                logger.info(
                    "atlas-%s | Wrote connmatrix aggregate (%d rows): %s",
                    atlas_name,
                    len(df),
                    out_path,
                )
                n_written += 1
        else:
            logger.info("No connmatrix CSVs found.")

    if not any_found:
        logger.error(
            "No qsiparc outputs found in %s%s.",
            qsiparc_dir,
            f" matching atlas filter {atlas_filter}" if atlas_filter else "",
        )
        sys.exit(2)

    click.echo(f"\nQSIParc aggregate complete: {n_written} file(s) written.")
    sys.exit(0)
