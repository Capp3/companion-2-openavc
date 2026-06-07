"""Unit tests for discovery extraction."""

from __future__ import annotations

from c2o.extract.discovery import extract_discovery
from c2o.model.driver import (
    CompatibleModelEntry,
    CompatibleModelsSection,
    ConfigFieldsSection,
    DiscoverySection,
    ManifestSection,
)
from c2o.model.review import ReviewCode


def _manifest(manufacturer: str) -> ManifestSection:
    return ManifestSection(
        id="dummy_device",
        name="Dummy Device",
        manufacturer=manufacturer,
        category="utility",
        version="1.0.0",
        author="C2O Fixture Bot",
        description="Fixture metadata.",
        source_url="https://github.com/Capp3/companion-2-openavc",
    )


def _config(port: object | None) -> ConfigFieldsSection:
    default_config = {} if port is None else {"port": port}
    return ConfigFieldsSection(default_config=default_config)


def _compat(*manufacturers: str) -> CompatibleModelsSection:
    return CompatibleModelsSection(
        compatible_models=tuple(
            CompatibleModelEntry(
                manufacturer=manufacturer,
                models=("Model",),
                confidence="untested",
            )
            for manufacturer in manufacturers
        )
    )


def test_extract_discovery_emits_port_aliases_and_missing_flag() -> None:
    section, review = extract_discovery(
        _manifest("Blackmagic Design"),
        _config(9977),
        _compat("Blackmagic Design"),
    )

    assert section == DiscoverySection(
        port_open=(9977,),
        manufacturer_alias=("blackmagic design", "blackmagic"),
    )
    flags = review.by_code(ReviewCode.MISSING_DISCOVERY_FINGERPRINT)
    assert len(flags) == 1
    assert flags[0].details["missing"] == (
        "mdns,ssdp,amx_ddp,tcp_probe,udp_probe,python,hostname,oui,snmp_pen"
    )


def test_extract_discovery_drops_disallowed_ports() -> None:
    section, review = extract_discovery(_manifest("Generic"), _config(8080), _compat())

    assert section.port_open == ()
    assert section.manufacturer_alias == ("generic",)
    assert review.has_code(ReviewCode.MISSING_DISCOVERY_FINGERPRINT)


def test_extract_discovery_coerces_string_port() -> None:
    section, _review = extract_discovery(_manifest("Generic"), _config("5000"), _compat())

    assert section.port_open == (5000,)


def test_extract_discovery_omits_missing_or_invalid_port() -> None:
    missing, _ = extract_discovery(_manifest("Generic"), _config(None), _compat())
    invalid, _ = extract_discovery(_manifest("Generic"), _config("abc"), _compat())

    assert missing.port_open == ()
    assert invalid.port_open == ()


def test_extract_discovery_does_not_add_variant_for_single_token_manufacturer() -> None:
    section, _review = extract_discovery(_manifest("Generic"), _config(5000), _compat("Generic"))

    assert section.manufacturer_alias == ("generic",)


def test_extract_discovery_uses_compatible_model_manufacturer_aliases() -> None:
    section, _review = extract_discovery(
        _manifest("Generic"),
        _config(5000),
        _compat("Vendor X", "generic"),
    )

    assert section.manufacturer_alias == ("generic", "vendor x", "vendor")


def test_extract_discovery_emits_curated_oui_hints_for_known_manufacturer() -> None:
    section, review = extract_discovery(
        _manifest("Panasonic"),
        _config(80),
        _compat("Panasonic"),
    )

    assert section.oui == ("00:80:45", "70:1d:7c", "00:60:b0")
    flags = review.by_code(ReviewCode.DISCOVERY_OUI_FROM_REGISTRY)
    assert len(flags) == 1
    assert flags[0].field == "discovery.oui"
    assert flags[0].details == {
        "manufacturer_alias": "panasonic",
        "oui": "00:80:45,70:1d:7c,00:60:b0",
    }
