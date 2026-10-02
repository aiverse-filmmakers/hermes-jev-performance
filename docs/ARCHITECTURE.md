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
│   ├── telemetry.py         # event creation and aggregation
│   ├── store.py             # SQLite schema/access
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

Defaults must be reviewed during implementation. First install SHOULD prefer `shadow` rather than silently enabling routing.

## 11. Telemetry storage

Use SQLite through Python's standard library unless an ADR changes this.

Benefits:

- transactional writes;
- compact local file;
- indexed dashboard queries;
- no external service;
- easy retention deletion;
- standard library dependency.

Schema is defined in `TELEMETRY.md`.

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

Dashboard backend responsibilities:

- status/mode read;
- mode write;
- aggregate metrics;
- recent decisions;
- comparison data;
- retention/clear action only with explicit confirmation design;
- health/compatibility information.

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
