"""Extract best-effort OpenAVC discovery hints."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

from c2o.model.driver import (
    CompatibleModelsSection,
    ConfigFieldsSection,
    DiscoverySection,
    ManifestSection,
)
from c2o.model.review import ReviewCode, ReviewFlag, ReviewReport

# Mirrors upstream avcdriver.schema.json discovery.port_open disallowed set.
_DISALLOWED_PORTS: Final[frozenset[int]] = frozenset({22, 80, 443, 8000, 8080, 8443, 8888})
_HAS_UPPER = re.compile(r"[A-Z]")
_MISSING_DISCOVERY_KEYS: Final[tuple[str, ...]] = (
    "mdns",
    "ssdp",
    "amx_ddp",
    "tcp_probe",
    "udp_probe",
    "python",
    "hostname",
    "oui",
    "snmp_pen",
)


class DiscoveryExtractionError(ValueError):
    """Raised when discovery extraction encounters unrecoverable input."""


def extract_discovery(
    manifest: ManifestSection,
    config_fields: ConfigFieldsSection,
    compatible_models: CompatibleModelsSection,
) -> tuple[DiscoverySection, ReviewReport]:
    """Build statically provable discovery hints and review flags."""
    section = DiscoverySection(
        port_open=_port_open(config_fields.default_config.get("port")),
        manufacturer_alias=_manufacturer_aliases(manifest, compatible_models),
    )
    return section, ReviewReport(flags=(_missing_discovery_flag(),))


def _port_open(raw_port: object) -> tuple[int, ...]:
    if isinstance(raw_port, bool) or not isinstance(raw_port, int | str):
        return ()
    try:
        port = int(raw_port)
    except (TypeError, ValueError):
        return ()
    if not (1 <= port <= 65535) or port in _DISALLOWED_PORTS:
        return ()
    return (port,)


def _manufacturer_aliases(
    manifest: ManifestSection,
    compatible_models: CompatibleModelsSection,
) -> tuple[str, ...]:
    values: list[str] = [manifest.manufacturer]
    variant = _brand_variant(manifest.manufacturer)
    if variant is not None:
        values.append(variant)

    for entry in compatible_models.compatible_models:
        values.append(entry.manufacturer)
        variant = _brand_variant(entry.manufacturer)
        if variant is not None:
            values.append(variant)

    return _dedup_case_insensitive(values)


def _brand_variant(name: str) -> str | None:
    head, _, tail = name.strip().partition(" ")
    if not tail or len(head) < 3 or _HAS_UPPER.search(head) is None:
        return None
    if head == name:
        return None
    return head


def _dedup_case_insensitive(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        value = raw.strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return tuple(out)


def _missing_discovery_flag() -> ReviewFlag:
    return ReviewFlag(
        code=ReviewCode.MISSING_DISCOVERY_FINGERPRINT,
        field="discovery",
        message=(
            "Companion modules do not statically expose mdns/ssdp/amx_ddp/"
            "tcp_probe/udp_probe/python/hostname/oui/snmp_pen fingerprints; "
            "extend by hand if the device supports them."
        ),
        details={"missing": ",".join(_MISSING_DISCOVERY_KEYS)},
    )
