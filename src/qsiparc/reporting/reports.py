"""Stub report builders."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ReportBuilder:
    """Build text or HTML summaries of a parcellation run."""

    output_dir: Path

    def write_summary(self, notes: list[str]) -> Path:
        """Write a minimal summary file."""

        self.output_dir.mkdir(parents=True, exist_ok=True)
        destination = self.output_dir / "summary.txt"
        destination.write_text("\n".join(notes) if notes else "No notes recorded.")
        return destination

