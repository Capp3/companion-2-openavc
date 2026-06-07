"""YAML suitability gate assessment."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from c2o.parse.js import ParsedModule, find_symbol_references
from c2o.suitability.blockers import Blocker, BlockerCode

_UPSTREAM_UDP_REF = "open-avc/openavc-drivers AGENTS.md §1 — UDP broadcast/multicast? Use Python."
_UPSTREAM_BINARY_REF = (
    "open-avc/openavc-drivers AGENTS.md §1 — Binary framing/checksums require Python."
)
_UPSTREAM_AUTH_REF = "open-avc/openavc-drivers AGENTS.md §1 — Custom auth schemes require Python."
_UPSTREAM_TRANSPORT_REF = (
    "open-avc/openavc-drivers AGENTS.md §1 — YAML drivers require a recognised transport."
)
_UPSTREAM_TRANSPORT_NOT_IMPLEMENTED_REF = (
    "open-avc/openavc-drivers AGENTS.md §1 — Use Python/manual authoring for transports "
    "C2O cannot currently express."
)
_UPSTREAM_COMMANDS_REF = (
    "open-avc/openavc-drivers AGENTS.md §1 — Cryptographic/challenge-response or "
    "computed payloads require Python."
)
_UPSTREAM_RESPONSES_REF = (
    "open-avc/openavc-drivers AGENTS.md §10 — Multi-line responses fan out per line. "
    "Stateful byte parsers require Python."
)

_AUTH_SEND_PATTERN = re.compile(
    r"\b(send|sendCommand)\b.*\b(LOGIN|AUTH|TOKEN|SESSION|Authorization|Bearer|access_token|apiKey)\b",
    re.IGNORECASE,
)
_KNOWN_TRANSPORT_PATTERNS = (
    "TCPHelper",
    "UDPHelper",
    "SerialPort",
    "fetch(",
    "axios",
    "got(",  # direct got() call
    "got.",  # got.get(), got.post(), etc. (method-style HTTP client)
    "node-fetch",
    "OSC",
    "osc-js",
    "osc-min",
)
_OSC_TRANSPORT_PATTERNS = (
    "from 'osc-js'",
    'from "osc-js"',
    "require('osc-js')",
    'require("osc-js")',
    "from 'osc-min'",
    'from "osc-min"',
    "require('osc-min')",
    'require("osc-min")',
    "new OSC",
    "sendOSC(",
    "sendOsc(",
    "oscSend(",
)
_VOLATILE_COMMAND_PATTERNS = (
    "Date.now(",
    "Math.random(",
    "crypto.randomBytes(",
    "crypto.randomUUID(",
    "process.hrtime(",
    "nonce(",
    "uuid(",
    ".randomUUID(",
)
_LINE_RESPONSE_SIGNALS = (
    "line.match(",
    "line.startsWith(",
    "line.endsWith(",
    "line.indexOf(",
    "line.split(",
    "chunk.indexOf(",
    "chunk.split(",
    "chunk.toString().split(",
    ".test(",
)


@dataclass(frozen=True)
class GateResult:
    """Outcome of running the suitability gate on a parsed module."""

    eligible: bool
    blockers: tuple[Blocker, ...]


def assess_module(parsed: ParsedModule) -> GateResult:
    """Run static suitability checks in stable §5.3 catalogue order."""
    blockers: list[Blocker] = []
    blockers.extend(_check_transport_udp(parsed))
    blockers.extend(_check_binary_framing(parsed))
    blockers.extend(_check_auth_non_telnet(parsed))
    blockers.extend(_check_transport_unknown(parsed))
    blockers.extend(_check_transport_not_implemented(parsed))
    blockers.extend(_check_commands_not_static(parsed))
    blockers.extend(_check_responses_not_expressible(parsed))
    return GateResult(eligible=not blockers, blockers=tuple(blockers))


def _check_transport_udp(parsed: ParsedModule) -> list[Blocker]:
    hits = find_symbol_references(parsed, "UDPHelper")
    if not hits:
        return []
    _rel, evidence = hits[0]
    return [
        Blocker(
            code=BlockerCode.TRANSPORT_UDP,
            message=(
                "Module uses UDPHelper; OpenAVC recommends a Python driver for UDP protocols."
            ),
            evidence=evidence,
            upstream_reference=_UPSTREAM_UDP_REF,
        )
    ]


def _check_binary_framing(parsed: ParsedModule) -> list[Blocker]:
    hit = _first_line_matching(
        parsed,
        lambda line: (
            "Buffer.alloc(" in line
            or "readUInt" in line
            or "writeUInt" in line
            or "writeInt" in line
            or "frameParser" in line
            or "frame_parser" in line
            or "parseFrame" in line
            or "buildFrame" in line
            or ("checksum" in line.lower() and ("^" in line or "& 0xff" in line))
            or ("crc" in line.lower() and ("^" in line or "& 0xff" in line))
        ),
    )
    if hit is None:
        return []
    return [
        Blocker(
            code=BlockerCode.BINARY_FRAMING,
            message="Binary framing detected; YAML drivers require text delimiters or HTTP.",
            evidence=hit,
            upstream_reference=_UPSTREAM_BINARY_REF,
        )
    ]


def _check_auth_non_telnet(parsed: ParsedModule) -> list[Blocker]:
    hit = _first_line_matching(parsed, lambda line: bool(_AUTH_SEND_PATTERN.search(line)))
    if hit is None:
        return []
    return [
        Blocker(
            code=BlockerCode.AUTH_NON_TELNET,
            message="Custom auth scheme; YAML supports auth: telnet_login only.",
            evidence=hit,
            upstream_reference=_UPSTREAM_AUTH_REF,
        )
    ]


def _check_transport_unknown(parsed: ParsedModule) -> list[Blocker]:
    for source in parsed.sources.values():
        if any(pattern in source for pattern in _KNOWN_TRANSPORT_PATTERNS):
            return []
    rel, _source = next(iter(parsed.sources.items()))
    return [
        Blocker(
            code=BlockerCode.TRANSPORT_UNKNOWN,
            message="Transport could not be inferred for YAML emission.",
            evidence=f"{rel}:1 — no recognised transport helper found",
            upstream_reference=_UPSTREAM_TRANSPORT_REF,
        )
    ]


def _check_transport_not_implemented(parsed: ParsedModule) -> list[Blocker]:
    hit = _first_line_matching(
        parsed,
        lambda line: any(pattern in line for pattern in _OSC_TRANSPORT_PATTERNS),
    )
    if hit is None:
        return []
    return [
        Blocker(
            code=BlockerCode.TRANSPORT_NOT_IMPLEMENTED,
            message=(
                "OSC transport detected; no OSC extractor is implemented. "
                "Decline this module and author the OpenAVC driver manually."
            ),
            evidence=hit,
            upstream_reference=_UPSTREAM_TRANSPORT_NOT_IMPLEMENTED_REF,
        )
    ]


def _check_commands_not_static(parsed: ParsedModule) -> list[Blocker]:
    for rel, source in parsed.sources.items():
        if "setActionDefinitions" not in source:
            continue
        for line_no, line in enumerate(source.splitlines(), start=1):
            if any(pattern in line for pattern in _VOLATILE_COMMAND_PATTERNS):
                return [
                    Blocker(
                        code=BlockerCode.COMMANDS_NOT_STATIC,
                        message=(
                            "One or more actions build commands dynamically at runtime; "
                            "cannot emit faithful send: templates."
                        ),
                        evidence=f"{rel}:{line_no} — {line.strip()}",
                        upstream_reference=_UPSTREAM_COMMANDS_REF,
                    )
                ]
    return []


def _check_responses_not_expressible(parsed: ParsedModule) -> list[Blocker]:
    for rel, source in parsed.sources.items():
        has_data_handler = (
            ".on('data'" in source
            or '.on("data"' in source
            or ".on('receiveline'" in source
            or '.on("receiveline"' in source
        )
        has_parser_state = (
            "this.parserState" in source
            or "this.parseState" in source
            or "this.parser.state" in source
        )
        has_switch = "switch (this.parserState" in source or "switch (this.parseState" in source
        has_line_signal = any(signal in source for signal in _LINE_RESPONSE_SIGNALS)
        if not (has_data_handler and has_parser_state and has_switch and not has_line_signal):
            continue
        evidence = _first_line_matching(
            ParsedModule(root=parsed.root, sources={rel: source}, trees={}),
            lambda line: "switch (this.parserState" in line or "switch (this.parseState" in line,
        )
        if evidence is None:
            evidence = f"{rel}:1 — parser-state response handler"
        return [
            Blocker(
                code=BlockerCode.RESPONSES_NOT_EXPRESSIBLE,
                message="Response parsing too complex for declarative responses matchers.",
                evidence=evidence,
                upstream_reference=_UPSTREAM_RESPONSES_REF,
            )
        ]
    return []


def _first_line_matching(
    parsed: ParsedModule,
    predicate: Callable[[str], bool],
) -> str | None:
    for rel, source in parsed.sources.items():
        for line_no, line in enumerate(source.splitlines(), start=1):
            if predicate(line):
                return f"{rel}:{line_no} — {line.strip()}"
    return None
