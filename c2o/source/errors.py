"""Source resolution errors."""

from __future__ import annotations


class SourceResolutionError(Exception):
    """Raised when a CLI source argument cannot be resolved to a module root."""
