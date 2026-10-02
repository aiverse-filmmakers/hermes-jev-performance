# Architecture

## 1. Architecture summary

Hermes Jev Performance is a **Hermes-native plugin plus Hermes dashboard extension**. It does not proxy Hermes' provider traffic and does not replace the main model.

```text
User / Telegram / CLI
        |
        v
      Hermes
        |
        | fresh user turn
        v
+---------------------------+
| hermes-jev-performance    |
|                           |
| Mode store                |
|   off / shadow / on       |
|        |                  |
|        v                  |
| Turn router --------------+------> OpenRouter Jev Decisions API
|        |                              |
|        | route/confidence/latency     |
|        <------------------------------+
|        |
|        v
| Tool policy
|  - accepted family -> filtered tools in ON
|  - SHADOW -> unchanged tools
|  - OFF/multi/low confidence/error -> unchanged tools
|        |
|        v
| Telemetry collector -> SQLite
+---------------------------+
        |
        v
 Hermes primary model/provider
        |
        v
 tools / tool loop / final answer

Hermes Dashboard
        |
        v
dashboard plugin UI -> /api/plugins/hermes-jev-performance/* -> SQLite/config
```

## 2. Public Hermes seams

The implementation should use supported Hermes surfaces only:

- Python plugin manifest and `register(ctx)` entry point;
- `llm_request` middleware for request/tool-list shaping where appropriate;
- Hermes hooks only where required for turn/usage telemetry;
- `ctx.register_command()` for `/jev` gateway/CLI slash commands;
- supported CLI subcommand APIs if needed;
- dashboard plugin directory with `manifest.json`, pre-built JS bundle and optional `plugin_api.py` FastAPI router;
- plugin-local configuration/state APIs.

No Hermes core file patch is part of the architecture.

## 3. Proposed repository layout

```text
hermes-jev-performance/
├── README.md
├── LICENSE
├── THIRD_PARTY_NOTICES.md
├── plugin.yaml
├── __init__.py
├── jevperf/
│   ├── client.py            # OpenRouter Jev transport
│   ├── config.py            # validated plugin settings
│   ├── modes.py             # off/shadow/on persistence
│   ├── routing.py           # Jev question + result parsing
│   ├── families.py          # family definitions and tool policy registry
│   ├── middleware.py        # Hermes llm_request integration
│   ├── commands.py          # /jev command parser/rendering
│   ├── benchmark.py         # fixture planning + paired delta math
│   ├── benchmark_context.py # process-scoped benchmark correlation/mode
│   ├── benchmark_runner.py  # explicit local read-only live runner
│   ├── benchmark_export.py  # anonymized JSON export
│   ├── telemetry.py         # event creation and aggregation
│   ├── store.py             # SQLite schema/access + benchmark storage
│   ├── compatibility.py     # Hermes capability/version detection
│   ├── doctor.py            # diagnostics
│   └── types.py             # internal typed records
├── dashboard/
│   ├── manifest.json
│   ├── dist/
│   │   └── index.js
│   └── plugin_api.py
├── benchmarks/
│   ├── fixtures/
│   └── runner.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── fixtures/
└── docs/
```

Exact file names may change through ADR, but module boundaries should remain.

## 4. Turn lifecycle

### 4.1 Fresh turn detection

The router acts only on a fresh user turn. It must use stable Hermes turn/session context rather than heuristics based solely on API-call count when Hermes exposes the identifiers.

Per-turn state key:

```text
(session_id, turn_id) -> RoutingDecision
```

The cached decision is reused for later provider calls in the same tool loop.

### 4.2 Mode behavior

**OFF**

1. Detect turn.
2. Do not call Jev.
3. Do not change tools.
4. Start/continue Hermes baseline telemetry.

**SHADOW**

1. Detect turn.
2. Call Jev once.
3. Record route/confidence/latency/cost.
4. Do not change tools.
5. Record Hermes outcome.

**ON**

1. Detect turn.
2. Call Jev once.
3. Validate route and threshold.
4. If accepted, derive allowed tool set.
5. If unsafe/uncertain/multi/empty/error, leave tools unchanged.
6. Record Hermes outcome.

## 5. Jev request contract

v1 asks one bounded choice question whose criteria describe the routing families. The exact request schema must follow the OpenRouter Decisions API and remain isolated in `client.py`/`routing.py`.

Conceptual state:

```json
{
  "state": "<redacted/capped user-turn text used only for live decision>",
  "questions": {
    "tool_family": {
      "type": "choice",
      "criteria": {
        "github": "...",
        "apps": "...",
        "web": "...",
        "terminal": "...",
        "files": "...",
        "memory": "...",
        "skills": "...",
        "media": "...",
        "none": "...",
        "multi": "..."
      }
    }
  }
}
```

The live turn text may be sent to Jev because routing requires semantic content, but it MUST NOT be stored in telemetry. Secret-like content should be locally redacted before the request where practical, following upstream safety patterns.

## 6. Routing acceptance policy

A decision is applyable only when all are true:

```text
mode == on
AND response valid
AND family known
AND family not in {multi}
AND confidence >= configured threshold
AND route maps to a valid tool policy
AND resulting allowed tool list is non-empty when tools are required
AND Hermes compatibility checks pass
```

Otherwise the plugin returns the original request unchanged.

## 7. Tool-family policy

`families.py` owns the mapping. It must support:

- exact tool names;
- stable prefixes/patterns where justified;
- per-install override/additions;
- an `always_keep` set for safety/control/escape tools;
- unknown-tool policy.

Initial semantic families:

| Family | Intended tools |
|---|---|
| github | GitHub-specific CLI/skills/tools required for repo/PR/issue work |
| apps | Hermes deferred app/MCP bridge tools |
| web | web search/extract/browser research tools |
| terminal | shell/command/code execution tools |
| files | local file read/search/write/patch tools |
| memory | memory tool(s) |
| skills | skill list/view/manage tools |
| media | vision/TTS/media analysis tools |
| none | no routing restriction required by v1 policy; telemetry records the classification |
| multi | explicitly unrestricted |

The exact mapping must be discovered/tested against supported Hermes versions rather than assuming one fixed global tool list.

## 8. Mixed-workflow protection

Hard single-family filtering can break requests such as "research a public issue and save a local report". v1 therefore adds `multi` as a first-class choice and uses conservative criteria.

Additional safeguards:

- low confidence -> unrestricted;
- zero mapped tools -> unrestricted;
- unknown tools -> preserved unless policy explicitly handles them;
- always-keep control/escape tools;
- optional future adaptive re-route may be added only after v1 evidence.

## 9. OpenRouter client

Requirements:

- endpoint isolated in one transport module;
- configurable Jev model;
- bounded timeout;
- no automatic cross-provider fallback;
- safe error normalization;
- capture provider-reported usage/cost when present;
- measure wall-clock request latency with monotonic time;
- never log request headers or token values;
- optional standard OpenRouter attribution headers may identify only this public project.

Credential preference:

1. dedicated Jev OpenRouter secret;
2. optional documented compatibility use of a generic OpenRouter credential;
3. no silent credential copying.

## 10. State and configuration

Recommended settings:

```yaml
mode: shadow
provider: openrouter
model: typesafe/jev-1.13
min_confidence: 0.70
timeout_seconds: 2.5
notice: false
retention_days: 30
telemetry_enabled: true
```

These are the implemented Phase 6 defaults. First install uses `shadow` rather than silently enabling behavioral routing.

## 11. Telemetry storage

Use SQLite through Python's standard library unless an ADR changes this.

Benefits:

- transactional writes;
- compact local file;
- indexed dashboard queries;
- no external service;
- easy retention deletion;
- standard library dependency.

Schema is defined in `TELEMETRY.md`. The current schema is version 2 and is stored under the active Hermes profile's `plugin-data/hermes-jev-performance/` directory.

## 12. Dashboard architecture

Hermes supports a plugin-local dashboard structure:

```text
<plugin>/dashboard/
├── manifest.json
├── dist/index.js
└── plugin_api.py
```

The UI must use Hermes' dashboard plugin SDK and the backend API must be mounted through Hermes under `/api/plugins/<name>/`.

The plugin MUST NOT start a second publicly exposed dashboard server for the normal Hermes integration.

Implemented Phase 7 dashboard backend responsibilities:

- `GET /status` for current mode/config + 24h summary;
- `GET /summary?hours=` for safe aggregate metrics;
- `GET /analytics?hours=&limit=` for route distribution, fallback reasons, time series, recent decision metadata and OFF/SHADOW/ON observational comparison;
- `PUT /mode` for validated off/shadow/on changes through Hermes' canonical plugin-settings writer with read-back verification;
- no prompt, tool payload, raw turn key or local filesystem path in dashboard responses;
- mode-change audit metadata written locally when telemetry storage is available.

The dashboard bundle calls these routes only through Hermes `SDK.fetchJSON`, which carries dashboard authentication. Hermes mounts plugin routes behind its normal dashboard auth gate.

### 12.1 Implemented dashboard UI

The `Jev Performance` tab is a pre-built Hermes SDK IIFE with theme-aware CSS. It currently provides:

- live OFF / SHADOW / ON status and mode control;
- Jev latency, confidence and provider-reported cost cards;
- route distribution;
- routing outcome/fallback breakdown;
- Hermes turn-duration, tool-call, LLM-request and token time-series charts;
- recent Jev decision metadata;
- OFF / SHADOW / ON observational comparison;
- controlled matched benchmark results;
- anonymized benchmark JSON export;
- 24h / 7d / 30d ranges;
- responsive/mobile layout.

The UI keeps ordinary usage labelled observational/not causal and renders controlled matched benchmark data in a separate section.

## 12.2 Controlled benchmark architecture

Phase 8 adds:

```text
hermes jev benchmark
        |
        | preview only by default
        v
read-only fixture suite
        |
        | --live explicitly required
        v
benchmark runner
        |
        +--> spawned Hermes process [OFF override]
        |
        +--> spawned Hermes process [ON override]
        |
        v
benchmark-tagged Hermes telemetry
        |
        v
SQLite schema v3
  - benchmark_runs
  - benchmark_samples
  - benchmark tags on hermes_turns
        |
        +--> paired delta engine
        +--> dashboard benchmark section
        +--> anonymized JSON export
```

The runner never changes the user's persistent Jev mode. OFF/ON is passed only to the spawned benchmark process after a full validated benchmark context is present.

Warm-ups are tagged and excluded from deltas. Measured pairs are matched by fixture ID plus repeat index. Mode order alternates on subsequent repeats to reduce simple time/provider drift.

Organic dashboard queries require `benchmark_run_id IS NULL`, so benchmark traffic cannot pollute ordinary usage charts.

## 13. Gateway/Telegram architecture

`ctx.register_command("jev", ...)` is the primary user-control seam. The command handler reads/writes the same mode/config store as the dashboard.

No Telegram-specific bot fork should be necessary. Messaging gateways receive the standard Hermes slash command through Hermes.

## 14. Compatibility layer

All Hermes-version-sensitive behavior lives in `compatibility.py`. It should feature-detect required public surfaces before use.

Compatibility states:

- `supported`: all required seams present;
- `degraded`: routing works but one or more metrics unavailable;
- `unsupported`: routing modification disabled; plugin status explains why; normal Hermes continues.

## 15. Failure model

| Failure | Required behavior |
|---|---|
| Jev timeout | unchanged Hermes request; record timeout metadata |
| HTTP/provider error | unchanged Hermes request; safe error code only |
| malformed Jev response | unchanged request |
| low confidence | unchanged request |
| unknown family | unchanged request |
| metrics DB unavailable | routing continues; metrics disabled/degraded |
| dashboard UI broken | agent routing/commands continue |
| dashboard API broken | agent routing/commands continue |
| unsupported Hermes API | disable affected feature, never patch core automatically |

## 16. Separation of concerns

The routing path must not depend on the dashboard. The dashboard must not be required for `/jev` commands. Telemetry failure must not break routing. Jev failure must not break Hermes.


## 17. Packaging and hardening

Phase 9 uses Hermes' native plugin lifecycle rather than a project-specific installer. The manifest declares `requires_hermes: ">=0.21.5"`, while runtime feature detection remains authoritative.

The plugin intentionally declares no third-party Python runtime dependencies. It uses Python's standard library plus public Hermes runtime APIs.

### 17.1 Diagnostics

The plugin provides local diagnostics through the Jev command surfaces. Checks cover Hermes public plugin capabilities, version identity when available, Python compatibility, config validation, credential presence without returning secret values, dashboard assets, benchmark fixtures and telemetry database health.

Diagnostics make zero provider/network calls.

### 17.2 Telemetry recovery

A corrupt metrics database never causes automatic deletion. Routing remains independent of telemetry. Explicit operator recovery quarantines damaged SQLite files before creating a clean current schema.

### 17.3 Repository gate

CI runs a conservative public-repository scanner before unit tests. It reports only rule identifiers and file paths, not matched secret values.


## 18. Deferred-tool bridge preservation

Hermes may replace MCP, non-core plugin, and explicitly deferred built-in tool schemas with the `tool_search`, `tool_describe`, and `tool_call` bridge.

The public `llm_request` middleware receives the already assembled model-facing request. It can remove eager schemas, but it does not own the session's pre-assembly deferred catalog used to validate `tool_call`.

Therefore ON-mode routing:

- removes known competing eager tool schemas;
- preserves unknown/custom tools;
- preserves `clarify` and `delegate_task`;
- preserves the Hermes deferred-tool bridge for every family.

This means Jev routing is intentionally **not** a security or authorization boundary. Normal Hermes tool permissions, approvals, session toolset scope, and Tool Search validation remain authoritative.
