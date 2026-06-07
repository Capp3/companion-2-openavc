# External Companion module fixtures

Real-world Bitfocus Companion modules vendored in-repo for integration and golden tests. Each fixture is pinned to the copy in this directory (no live network in tests).

## Source-resolution smoke fixture

The source-resolution tests build a temporary bare `file://` git mirror from `tests/fixtures/dummy-device/` at test runtime. This keeps URL and bare-ID smoke tests offline while still exercising real `git clone --depth 1`.

## `bmd-webpresenter/`

Blackmagic Design Web Presenter module (TCP, newline-delimited key/value protocol). Exercises multi-line response fan-out, string-template commands, and polling patterns that the purpose-built `dummy-device` fixture does not cover. Used from M3 onward for gate eligibility and extractor goldens.

## `panasonic-ptz/`

Panasonic PTZ Camera module (HTTP CGI, `got` library). Pinned from `bitfocus/companion-module-panasonic-ptz` at commit `89c9f0a79d1a70c4e66a8590a0fff2964bd26ba9`.

This fixture exercises the **`src/` source layout** used by newer Companion modules — all JS source files live under `src/` rather than at the module root. It is paired with the independently-authored `panasonic_awhe.avcdriver` in `tests/golden/` which serves as the **ground-truth diff target**: run C2O against this fixture, compare to the golden, and each diff is an extractor bug to fix.

Key characteristics: HTTP transport via `got.get()`/`got.post()`, model-specific variable and action sets, multi-file module (actions, variables, feedbacks, presets, config, choices, models all in separate files).

`icons.js` is deliberately excluded from the snapshot — it contains only base64 icon asset strings and has no extractable Companion logic.
