# Companion-2-OpenAVC (C2O)

Convert **Bitfocus Companion** modules into **OpenAVC** `.avcdriver` driver definitions.

## Status

This repository is currently in **design / pre-implementation**. The files here (especially [`avcdriverbreakdown.avcdriver`](avcdriverbreakdown.avcdriver)) describe the intended output shape and the mapping from a Companion module to an OpenAVC driver.

## What & why

Bitfocus Companion modules are typically **imperative Node.js code** (actions with callbacks that build protocol strings, TCP/UDP helpers, response parsing, polling loops).

OpenAVC drivers are intended to be **declarative**: metadata, config schema, commands, response matchers, and polling defined as structured data (YAML-style).

The goal of C2O is to **lift** the “what” from a Companion module into an OpenAVC driver so that:

- the same device definition can be reused outside Companion
- driver behaviour can be reasoned about and tested as data
- drivers can be generated/maintained consistently from existing Companion ecosystems

## How it works (intended)

```mermaid
flowchart LR
  companionModule[CompanionModule\n(manifest+js)] --> c2o[C2OConverter\n(parser+extractors)]
  c2o --> avc[OpenAVCDriver\n(.avcdriver)]
```

## Concept mapping: Companion → `.avcdriver`

The best “current spec” for the target output is the top of [`avcdriverbreakdown.avcdriver`](avcdriverbreakdown.avcdriver). It’s a breakdown file that uses placeholders like `<path:json_pointer>` to show where values should come from.

Using the included example module at [`example/companion-module-bmd-webpresenter/`](example/companion-module-bmd-webpresenter/), here’s the intended mapping:

- **Driver metadata**
  - **Source**: [`example/companion-module-bmd-webpresenter/companion/manifest.json`](example/companion-module-bmd-webpresenter/companion/manifest.json)
  - **Target**: `id`, `name`, `manufacturer`, `description`, `version`

- **Category / author (prompted)**
  - **Source**: user input (there isn’t a canonical field in Companion’s manifest for all of these)
  - **Target**: `category`, `author` (and optionally `version` if you want to override the manifest)

- **Transport / delimiter**
  - **Source**: module runtime code, e.g. [`example/companion-module-bmd-webpresenter/index.js`](example/companion-module-bmd-webpresenter/index.js)
    - transport inference example: `TCPHelper(...)` suggests TCP
    - delimiter inference example: buffering and splitting on `\n` suggests newline-delimited messages
  - **Target**: `transport`, `delimiter` (exact OpenAVC fields pending final spec)

- **Configuration schema**
  - **Source**: `getConfigFields()` in `index.js` (Companion UI fields like `host`, `port`)
  - **Target**:
    - `default_config` (defaults for the driver)
    - `config_schema` (type/required/labels/min/etc.)

- **State variables**
  - **Source**: `setVariableDefinitions(...)` in [`example/companion-module-bmd-webpresenter/variables.js`](example/companion-module-bmd-webpresenter/variables.js)
  - **Target**: `state_variables` (typed, labelled variables that OpenAVC can expose)

- **Commands (actions)**
  - **Source**: `setActionDefinitions(...)` in [`example/companion-module-bmd-webpresenter/actions.js`](example/companion-module-bmd-webpresenter/actions.js)
    - actions often build strings like `cmd = 'STREAM STATE:\\nAction: ' + ... + '\\n\\n'`
  - **Target**: `commands`
    - `send` templates (string templates with parameters)
    - `params` (typed parameters with help)

- **Responses (parsing)**
  - **Source**: socket parsing / regex matching in the module, typically in `index.js` (`on('data')`, `on('receiveline')`, regexes, object extraction)
  - **Target**: `responses`
    - `match`: regex pattern
    - `set`: variable assignments (capture groups → state variables)

- **Polling**
  - **Source**: recurring timers like `setInterval(...dataPoller...)` and whatever command strings are sent
  - **Target**: `polling.interval` and `polling.queries`

## Planned CLI

The initial interface is intended to be a CLI. Proposed shape (subject to change as the implementation lands):

```bash
# Convert a Companion module to an OpenAVC driver file
c2o convert ./path/to/companion-module -o driver.avcdriver

# Prompt for fields that aren't safely inferrable (category/author/etc.)
c2o convert ./path/to/companion-module -o driver.avcdriver --interactive

# Dry-run: show what the converter thinks it can extract
c2o inspect ./path/to/companion-module
```

## Try the included reference example (input fixture)

- **Example module**: [`example/companion-module-bmd-webpresenter/`](example/companion-module-bmd-webpresenter/)
- **Target output breakdown**: [`avcdriverbreakdown.avcdriver`](avcdriverbreakdown.avcdriver)

This example is useful because it covers a common pattern: TCP transport, newline-delimited responses, commands as string templates, and polling.

## Open design questions (tracked in `avcdriverbreakdown.avcdriver`)

These are explicitly called out as placeholders near the top of [`avcdriverbreakdown.avcdriver`](avcdriverbreakdown.avcdriver) and still need decisions:

- **`transport`**: how reliably can we infer TCP vs UDP vs HTTP vs IPC from module code across the ecosystem?
- **`delimiter`**: should this be a fixed delimiter (like `\n`) or a regex splitter, and how do we express multi-line message blocks?
- **`help.overview` / `help.setup`**: should these be pulled from the module’s `README`/`HELP.md` (when present) or always prompted for?
- **Coverage**: how do we represent Companion concepts that don’t map cleanly (feedbacks, presets) in the first version?

## Repository layout (current)

```sh
.
├─ avcdriverbreakdown.avcdriver        # Target output breakdown/spec template
├─ example/
│  └─ companion-module-bmd-webpresenter/  # Reference Companion module fixture
├─ docs/                               # MkDocs content (currently a stub)
└─ README.md
```

## Roadmap (high-level)

- **Manifest extraction**: read `manifest.json` → driver metadata
- **Config schema extraction**: read `getConfigFields()` → config schema + defaults
- **Action extraction**: convert `setActionDefinitions()` into `commands` with parameters and `send` templates
- **Response extraction**: extract regex/line parsing into `responses`
- **Transport + delimiter inference**: implement heuristics for common patterns (`TCPHelper`, newline framing, etc.)
- **Interactive prompts**: for `category`, `author`, and any non-inferrable fields
- **Validation**: ensure output matches the required `.avcdriver` schema and aligns with the breakdown template

## Resources

### OpenAVC

- `https://docs.openavc.com/`
- `https://github.com/open-avc/openavc`

### Companion

- `https://bitfocus.io/companion`
- `https://github.com/bitfocus/companion`
- `https://companion.free/`

## License

MIT (see [`LICENCE`](LICENCE)).
