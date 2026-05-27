"""Decline blocker models for the YAML suitability gate."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class BlockerCode(StrEnum):
    """Stable blocker codes (§5.3). M1 implements transport_udp only."""

    TRANSPORT_UDP = "transport_udp"


class Blocker(BaseModel):
    """A single gate blocker with user-facing context."""

    model_config = ConfigDict(frozen=True)

    code: BlockerCode
    message: str
    evidence: str
    upstream_reference: str
