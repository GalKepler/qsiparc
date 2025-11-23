"""Atlas alignment and resampling placeholders."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AtlasTransform:
    """Describe how an atlas should be aligned to subject space."""

    atlas_to_template: Path | None = None
    template_to_subject: Path | None = None

    def is_configured(self) -> bool:
        """Return True when any transform is configured."""

        return bool(self.atlas_to_template or self.template_to_subject)

