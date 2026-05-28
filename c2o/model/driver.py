"""Pydantic models for OpenAVC driver sections."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DriverCategory = Literal[
    "projector",
    "display",
    "switcher",
    "audio",
    "camera",
    "video",
    "streaming",
    "lighting",
    "power",
    "utility",
]

DriverTransport = Literal["tcp", "serial", "udp", "http", "osc"]

ConfigFieldType = Literal["string", "text", "integer", "number", "float", "boolean", "enum"]

StateVariableType = Literal["string", "integer", "number", "float", "boolean", "enum"]


class ManifestSection(BaseModel):
    """Top-level metadata fields sourced from Companion manifest.json."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1)
    manufacturer: str = Field(min_length=1)
    category: DriverCategory
    version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:[\-+][\w.\-]+)?$")
    author: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_url: str | None = Field(default=None, pattern=r"^[Hh][Tt][Tt][Pp][Ss]?://")


class TransportSection(BaseModel):
    """Top-level transport fields inferred from Companion JavaScript sources."""

    model_config = ConfigDict(frozen=True)

    transport: DriverTransport
    delimiter: str | None = None


class ConfigSchemaEntry(BaseModel):
    """A single OpenAVC config_schema entry."""

    model_config = ConfigDict(frozen=True)

    type: ConfigFieldType
    label: str | None = None
    default: Any = None
    required: bool | None = None
    values: tuple[str, ...] | None = None
    min: int | float | None = None
    max: int | float | None = None
    regex: str | None = None
    help: str | None = None
    description: str | None = None
    secret: bool | None = None


ParamEntry = ConfigSchemaEntry


class ConfigFieldsSection(BaseModel):
    """OpenAVC default_config and config_schema extracted from getConfigFields()."""

    model_config = ConfigDict(frozen=True)

    default_config: dict[str, Any] = Field(default_factory=dict)
    config_schema: dict[str, ConfigSchemaEntry] = Field(default_factory=dict)


class StateVariableEntry(BaseModel):
    """A single OpenAVC state_variables entry."""

    model_config = ConfigDict(frozen=True)

    label: str = Field(min_length=1)
    type: StateVariableType | None = None
    help: str | None = None
    values: tuple[str, ...] | None = None
    min: int | float | None = None
    max: int | float | None = None
    unit: str | None = None
    default: Any = None


class StateVariablesSection(BaseModel):
    """OpenAVC state_variables extracted from setVariableDefinitions()."""

    model_config = ConfigDict(frozen=True)

    state_variables: dict[str, StateVariableEntry] = Field(default_factory=dict)


class CommandEntry(BaseModel):
    """A single OpenAVC commands entry."""

    model_config = ConfigDict(frozen=True)

    label: str = Field(min_length=1)
    send: str = Field(min_length=1)
    help: str | None = None
    params: dict[str, ParamEntry] = Field(default_factory=dict)


class CommandsSection(BaseModel):
    """OpenAVC commands extracted from setActionDefinitions()."""

    model_config = ConfigDict(frozen=True)

    commands: dict[str, CommandEntry] = Field(default_factory=dict)
