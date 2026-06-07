"""Unit tests for storeData/checkVariables response parsing."""

from __future__ import annotations

from pathlib import Path

from c2o.parse.js import ParsedModule, parse_module, parse_source
from c2o.parse.store_data import (
    CapturedField,
    ConstantValue,
    SuffixCapture,
    TransformedValue,
    decode_store_data,
    find_check_variables_sink_map,
)


def _parsed_sources(sources: dict[str, str]) -> ParsedModule:
    return ParsedModule(
        root=Path("."),
        sources=sources,
        trees={path: parse_source(source) for path, source in sources.items()},
    )


def test_find_check_variables_sink_map_resolves_exported_function() -> None:
    parsed = _parsed_sources(
        {
            "src/variables.js": """
            export function checkVariables(self) {
              const gainValue = null
              self.setVariableValues({
                power: self.data.power,
                OAF: self.data.oaf,
                gainValue: gainValue?.label,
                ptSpeedVar: self.ptSpeed,
              })
            }
            """,
        }
    )

    assert find_check_variables_sink_map(parsed) == {
        "power": "power",
        "oaf": "OAF",
        "gainValue": None,
    }


def test_decode_store_data_handles_switch_and_prefix_patterns() -> None:
    parsed = _parsed_sources(
        {
            "src/index.js": """
            class Example {
              storeData(str) {
                if (str[0].substring(0, 4) === 'qSV3') {
                  this.data.version = str[0].substring(4)
                }
                switch (str[0]) {
                  case 'p1':
                    this.data.power = 'ON'
                    break
                  case 'OID':
                    this.data.model = str[1]
                    break
                  case 'TLR':
                    if (str[1] == '0') {
                      this.data.tally = 'OFF'
                    } else if (str[1] == '1') {
                      this.data.tally = 'ON'
                    }
                    break
                  case 'OSD':
                    if (str[1] == 'B1') {
                      this.data.colorTemperature = str[2]
                    }
                    break
                  case 'OGU':
                    this.data.gainValue = str[1].toString().replace('0x', '')
                    break
                }
              }
            }
            """,
        }
    )

    triples = {(t.token, t.field): t.value for t in decode_store_data(parsed)}

    assert triples[("p1", "power")] == ConstantValue("ON")
    assert triples[("OID", "model")] == CapturedField(1)
    assert triples[("TLR:0", "tally")] == ConstantValue("OFF")
    assert triples[("TLR:1", "tally")] == ConstantValue("ON")
    assert triples[("OSD:B1", "colorTemperature")] == CapturedField(2)
    assert triples[("qSV3", "version")] == SuffixCapture(prefix="qSV3", prefix_len=4)
    assert isinstance(triples[("OGU", "gainValue")], TransformedValue)


def test_panasonic_store_data_fixture_decodes_representative_triples(
    panasonic_ptz: Path,
) -> None:
    parsed = parse_module(panasonic_ptz)

    sink_map = find_check_variables_sink_map(parsed)
    triples = {(t.token, t.field): t.value for t in decode_store_data(parsed)}

    assert sink_map["power"] == "power"
    assert sink_map["oaf"] == "OAF"
    assert sink_map["gainValue"] is None
    assert triples[("p1", "power")] == ConstantValue("ON")
    assert triples[("dA1", "tally")] == ConstantValue("ON")
    assert triples[("TLR:0", "tally")] == ConstantValue("OFF")
    assert triples[("TLR:1", "tally")] == ConstantValue("ON")
    assert triples[("qSV3", "version")] == SuffixCapture(prefix="qSV3", prefix_len=4)
    assert ("rER", "error") not in triples
