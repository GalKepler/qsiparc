"""Command-line entrypoints for qsiparc."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path

from qsiparc.config import AtlasSelection, MetricSelection, ParcellationConfig
from qsiparc.reporting.reports import ReportBuilder
from qsiparc.workflows.runner import WorkflowRunner


def build_parser() -> argparse.ArgumentParser:
    """Return the top-level argument parser."""

    parser = argparse.ArgumentParser(description="Parcellate QSIRecon outputs into atlas-level summaries.")
    parser.add_argument("--input-root", required=True, type=Path, help="Root directory containing QSIRecon outputs.")
    parser.add_argument("--output-root", required=True, type=Path, help="Destination for parcellation outputs.")
    parser.add_argument("--subject", action="append", required=True, help="Subject label to include (repeatable).")
    parser.add_argument(
        "--atlas",
        action="append",
        default=[],
        type=Path,
        help="Path to an atlas file/directory (repeatable). Name is derived from the stem.",
    )
    parser.add_argument("--profile", default="volume", choices=["volume"], help="Processing profile.")
    return parser


def parse_config(args: argparse.Namespace) -> ParcellationConfig:
    """Translate CLI arguments into a ParcellationConfig."""

    atlases: list[AtlasSelection] = [AtlasSelection(name=path.stem, path=path) for path in args.atlas]
    metrics = MetricSelection(names=("mean", "median"), connectivity=False)
    return ParcellationConfig(
        input_root=args.input_root,
        output_root=args.output_root,
        subjects=args.subject,
        atlases=atlases,
        metrics=metrics,
        profile=args.profile,
    )


def run_cli(argv: Iterable[str] | None = None) -> int:
    """Entry point for CLI usage."""

    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    config = parse_config(args)
    config.ensure_output_root()
    runner = WorkflowRunner()
    runner.preload_atlases(atlas_root=config.input_root, selections=config.atlases)
    provenance = runner.run(config)
    report = ReportBuilder(output_dir=config.output_root / "reports")
    report.write_summary(notes=provenance.notes)
    return 0


def main() -> None:  # pragma: no cover - thin CLI wrapper
    run_cli()


if __name__ == "__main__":  # pragma: no cover
    main()
