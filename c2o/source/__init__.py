"""Source resolution for local paths, URLs, and bare module IDs."""

from c2o.source.classify import SourceKind, classify_source, expand_bare_id
from c2o.source.errors import SourceResolutionError
from c2o.source.local import read_module_id, resolve_local
from c2o.source.resolver import ResolvedSource, resolve_source

__all__ = [
    "ResolvedSource",
    "SourceKind",
    "SourceResolutionError",
    "classify_source",
    "expand_bare_id",
    "read_module_id",
    "resolve_local",
    "resolve_source",
]
