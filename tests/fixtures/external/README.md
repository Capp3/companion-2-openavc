# External Companion module fixtures

Real-world Bitfocus Companion modules vendored in-repo for integration and golden tests. Each fixture is pinned to the copy in this directory (no live network in tests).

## `bmd-webpresenter/`

Blackmagic Design Web Presenter module (TCP, newline-delimited key/value protocol). Exercises multi-line response fan-out, string-template commands, and polling patterns that the purpose-built `dummy-device` fixture does not cover. Used from M3 onward for gate eligibility and extractor goldens.
