"""Pydantic models for OpenAVC driver sections."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
CompatibleModelConfidence = Literal["full", "partial", "untested"]
HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH"]


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
    help: str | None = None
    params: dict[str, ParamEntry] = Field(default_factory=dict)
    send: str | None = Field(default=None, min_length=1)
    method: HttpMethod | None = None
    path: str | None = Field(default=None, min_length=1)
    body: str | None = None
    headers: dict[str, str] | None = None
    query_params: dict[str, str] | None = None

    @model_validator(mode="after")
    def _validate_command_shape(self) -> CommandEntry:
        has_send = self.send is not None
        has_method = self.method is not None
        has_path = self.path is not None
        has_http = has_method or has_path

        if has_send and has_http:
            msg = "CommandEntry cannot mix `send` with HTTP fields"
            raise ValueError(msg)
        if not has_send and not has_http:
            msg = "CommandEntry must declare either `send` or `method`+`path`"
            raise ValueError(msg)
        if has_http and (not has_method or not has_path):
            msg = "HTTP CommandEntry requires both `method` and `path`"
            raise ValueError(msg)
        if has_send and (
            self.body is not None or self.headers is not None or self.query_params is not None
        ):
            msg = "CommandEntry with `send` cannot set HTTP-only fields"
            raise ValueError(msg)

        return self


class CommandsSection(BaseModel):
    """OpenAVC commands extracted from setActionDefinitions()."""

    model_config = ConfigDict(frozen=True)

    commands: dict[str, CommandEntry] = Field(default_factory=dict)


ResponseMappingType = Literal["string", "integer", "float", "number", "boolean"]


class ResponseMappingEntry(BaseModel):
    """A single verbose response mapping row (upstream mappings[])."""

    model_config = ConfigDict(frozen=True)

    group: int
    state: str = Field(min_length=1)
    type: ResponseMappingType | None = None
    map: dict[str, bool | str | int | float] | None = None
    value: bool | str | int | float | None = None


class ResponseEntry(BaseModel):
    """A single OpenAVC responses[] entry."""

    model_config = ConfigDict(frozen=True)

    match: str = Field(min_length=1)
    set: dict[str, str] | None = None
    mappings: tuple[ResponseMappingEntry, ...] | None = None

    @model_validator(mode="after")
    def _validate_set_xor_mappings(self) -> ResponseEntry:
        has_set = self.set is not None and len(self.set) > 0
        has_mappings = self.mappings is not None and len(self.mappings) > 0
        if has_set == has_mappings:
            msg = "ResponseEntry requires exactly one of set or mappings"
            raise ValueError(msg)
        return self


class ResponsesSection(BaseModel):
    """OpenAVC responses extracted from receive handlers."""

    model_config = ConfigDict(frozen=True)

    responses: tuple[ResponseEntry, ...] = ()


class PollingSection(BaseModel):
    """OpenAVC polling queries and optional inferred poll cadence."""

    model_config = ConfigDict(frozen=True)

    queries: tuple[str, ...] = ()
    inferred_poll_interval: int | None = None


class DiscoverySection(BaseModel):
    """OpenAVC discovery hints that can be statically inferred."""

    model_config = ConfigDict(frozen=True)

    port_open: tuple[int, ...] = ()
    manufacturer_alias: tuple[str, ...] = ()


class CompatibleModelEntry(BaseModel):
    """A specific group of device models supported by the driver."""

    model_config = ConfigDict(frozen=True)

    manufacturer: str = Field(min_length=1)
    models: tuple[str, ...] = Field(min_length=1)
    confidence: CompatibleModelConfidence
    notes: str | None = None


class CompatibleModelsSection(BaseModel):
    """OpenAVC compatible_models entries extracted from Companion products."""

    model_config = ConfigDict(frozen=True)

    compatible_models: tuple[CompatibleModelEntry, ...] = ()


class OnConnectSection(BaseModel):
    """Static commands sent immediately after connecting to the device."""

    model_config = ConfigDict(frozen=True)

    commands: tuple[str, ...] = ()


class HelpSection(BaseModel):
    """OpenAVC help text extracted from Companion HELP.md."""

    model_config = ConfigDict(frozen=True)

    overview: str = Field(min_length=1)
    setup: str = Field(min_length=1)
