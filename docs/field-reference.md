# Field Reference

C2O does **not** maintain a parallel OpenAVC schema. Every field name, type, enum, and validation rule
comes from the upstream specification.

## Authoritative spec

- [open-avc/openavc-drivers/AGENTS.md](https://github.com/open-avc/openavc-drivers/blob/main/AGENTS.md)

## Authoritative validator

- [open-avc/openavc-drivers/scripts/build_index.py](https://github.com/open-avc/openavc-drivers/blob/main/scripts/build_index.py)

A pinned copy is vendored at `c2o/vendored/openavc_drivers/scripts/build_index.py` and refreshed via
`make update-upstream`.

## Historical note

The pre-upstream scratchpad `docs/legacy/avcdriverbreakdown.avcdriver` is retained for reference only.
Where it disagrees with upstream AGENTS.md, **upstream wins**.
