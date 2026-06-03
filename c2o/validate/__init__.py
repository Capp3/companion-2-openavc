"""Validation helpers for generated OpenAVC drivers.

M20 ships the authoritative upstream validation tier. The local pydantic tier
lands with the YAML emitter, when C2O has a complete driver model to validate.
"""

from c2o.validate.upstream import UpstreamValidationResult, validate_upstream

__all__ = ["UpstreamValidationResult", "validate_upstream"]
