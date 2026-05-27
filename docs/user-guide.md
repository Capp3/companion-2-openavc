# User Guide

!!! note "Coming in M23"
    Full user documentation will land with milestone M23. This page is a placeholder.

## Planned usage

```bash
# Convert a local Companion module clone
c2o convert ./companion-module-bmd-webpresenter -o bmd-webpresenter.avcdriver

# Inspect eligibility and extraction summary (dry run)
c2o inspect bmd-webpresenter

# Validate an existing .avcdriver against upstream rules
c2o validate ./bmd-webpresenter.avcdriver
```

See the [repository README](https://github.com/Capp3/companion-2-openavc) for the current CLI status.
