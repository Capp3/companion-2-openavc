"""YAML suitability gate assessment."""

from __future__ import annotations

from dataclasses import dataclass

from c2o.parse.js import ParsedModule, find_symbol_references
from c2o.suitability.blockers import Blocker, BlockerCode

_UPSTREAM_UDP_REF = "open-avc/openavc-drivers AGENTS.md §1 — UDP broadcast/multicast? Use Python."


@dataclass(frozen=True)
class GateResult:
    """Outcome of running the suitability gate on a parsed module."""

    eligible: bool
    blockers: tuple[Blocker, ...]


def assess_module(parsed: ParsedModule) -> GateResult:
    """Run static suitability checks. M1: transport_udp only (M3 adds more rules)."""
    blockers: list[Blocker] = []
    blockers.extend(_check_transport_udp(parsed))
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
