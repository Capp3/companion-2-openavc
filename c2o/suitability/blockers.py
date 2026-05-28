"""Decline blocker models for the YAML suitability gate."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class BlockerCode(StrEnum):
    """Stable blocker codes (§5.3)."""

    TRANSPORT_UDP = "transport_udp"
    BINARY_FRAMING = "binary_framing"
    AUTH_NON_TELNET = "auth_non_telnet"
    TRANSPORT_UNKNOWN = "transport_unknown"
    COMMANDS_NOT_STATIC = "commands_not_static"
    RESPONSES_NOT_EXPRESSIBLE = "responses_not_expressible"


class Blocker(BaseModel):
    """A single gate blocker with user-facing context."""

    model_config = ConfigDict(frozen=True)

    code: BlockerCode
    message: str
    evidence: str
    upstream_reference: str
