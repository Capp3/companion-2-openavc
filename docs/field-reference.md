# Field Reference

C2O does not maintain a parallel OpenAVC schema. Every `.avcdriver` field name, type, enum, and validation rule comes from upstream.

## Authoritative Spec

- [open-avc/openavc-drivers/AGENTS.md](https://github.com/open-avc/openavc-drivers/blob/main/AGENTS.md)

Use that document for the prose contract for every field C2O emits.

## Authoritative Validator

- [open-avc/openavc-drivers/scripts/build_index.py](https://github.com/open-avc/openavc-drivers/blob/main/scripts/build_index.py)

A pinned copy is vendored at `c2o/vendored/openavc_drivers/scripts/build_index.py` and refreshed via:

```bash
make update-upstream
```

`c2o validate` runs this validator against existing `.avcdriver` files through an isolated temporary catalog.

## Companion Sibling Files

C2O also preserves some Companion-only surfaces as informational sibling files:

- `.companion-feedbacks.yml`
- `.companion-presets.yml`

These files are not `.avcdriver` fields, are not part of the OpenAVC catalog, and are ignored by `build_index.py`.

## Historical Note

The pre-upstream scratchpad `docs/legacy/avcdriverbreakdown.avcdriver` is retained for reference only.
Where it disagrees with upstream AGENTS.md, **upstream wins**.
