"""Lightweight provenance tracking for runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RunProvenance:
    """Record configuration and artifacts produced in a run."""

    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    parameters: dict[str, str] = field(default_factory=dict)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def mark_finished(self) -> None:
        """Mark the run as finished."""

        self.finished_at = datetime.utcnow()

    def record_input(self, path: str) -> None:
        """Add an input path to the provenance."""

        self.inputs.append(path)

    def record_output(self, path: str) -> None:
        """Add an output path to the provenance."""

        self.outputs.append(path)

    def add_note(self, message: str) -> None:
        """Attach a human-readable note."""

        self.notes.append(message)

