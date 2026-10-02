# Upstream Projects and Provenance

This project intentionally combines ideas from multiple MIT-licensed projects while keeping a Hermes-native architecture.

## Reference snapshot

The initial architecture was researched against these public snapshots:

| Project | Repository | Reference commit observed during planning | Role |
|---|---|---|---|
| Hermes Jev Skills | https://github.com/kerpopule/hermes-jev-skills | `4e9b3677a9d482d661419441782589883634cfe3` | Hermes plugin patterns, `/jev`, shadow/on/off UX, routing lifecycle, dashboard concepts |
| jev-gateway | https://github.com/vinilana/jev-gateway | `38f2923dc388a5bf7b1b3bb7308f30477256cd8c` | observability, latency/cost/tokens, recent requests, baseline comparisons |
| Hermes Jev | https://github.com/ourines/hermes-jev | `cdf59e46270d3b33618d3b275c5c2fb76f594a19` | Hermes-native Jev plugin structure and OpenRouter Decisions backend |
| Hermes Agent | https://github.com/NousResearch/hermes-agent | public `main` around `b3059921bc02b94e90fb6c0cdfe07bd16005fbba` during planning | supported plugin/middleware/command/dashboard APIs |

These hashes are provenance references, not permanent dependency pins. Any actual copied source file must document its own source/reference.

## 1. kerpopule/hermes-jev-skills

Repository: https://github.com/kerpopule/hermes-jev-skills

Observed useful features:

- `hermes-jev` Hermes plugin;
- `llm_request` middleware;
- `/jev` command;
- on/shadow/off feature switches;
- fresh-turn decision reuse through the tool loop;
- routing dashboard;
- per-decision confidence and latency;
- explicit privacy/redaction thinking;
- fail-open patterns.

v1 adoption:

- reuse/adapt Hermes-native patterns and command UX where they fit;
- reuse dashboard ideas;
- do **not** automatically import its broader memory/search/screening/GUI/mailbox feature set.

Phase 2 concrete adoption:

- `jevperf/client.py` also adopts selected validation/transport safety ideas from `jevkit/client.py`, while deliberately avoiding its broader provider matrix and connection-pool complexity in the first OpenRouter-only implementation.

## 2. vinilana/jev-gateway

Repository: https://github.com/vinilana/jev-gateway

Observed useful features:

- dashboard status states;
- Jev calls/latency/confidence/cost;
- LLM token fields;
- seconds per request;
- recent request table;
- routing on/off baseline mode;
- side-by-side baseline comparison.

v1 adoption:

- reuse/adapt metric definitions and dashboard interaction patterns;
- possibly reuse isolated MIT-licensed UI/aggregation code with attribution;
- **do not adopt the proxy/gateway architecture**;
- do not place Hermes provider traffic behind a new local proxy.

## 3. ourines/hermes-jev

Repository: https://github.com/ourines/hermes-jev

Observed useful features:

- Hermes-native plugin manifest;
- OpenRouter backend using the Jev Decisions endpoint;
- default OpenRouter model `typesafe/jev-1.13`;
- bounded request/service layer;
- safe error handling;
- credential separation;
- latency/usage return data;
- fail-open model-routing patterns.

v1 adoption:

- reuse/adapt the OpenRouter client/provider logic;
- reuse safety/credential patterns where compatible;
- do not enable its automatic model switching in v1.

Phase 2 concrete adoption:

- `jevperf/client.py` is adapted in part from upstream `client.py` at the reference commit above, reduced to the OpenRouter-only surface required by this project;
- response validation, bounded payload/response handling, safe error categories and no-automatic-retry behavior follow the upstream safety model;
- `jevperf/credentials.py` uses a dedicated Jev credential first while supporting a documented generic OpenRouter compatibility fallback;
- the default remains the pinned `typesafe/jev-1.13` model for reproducible performance comparisons. The OpenRouter alias `~typesafe/jev-latest` is accepted as an explicit configurable override rather than silently changing benchmark model versions.

## 4. NousResearch/hermes-agent

Repository: https://github.com/NousResearch/hermes-agent

Relevant public APIs/documentation:

- general Python plugin API;
- `ctx.register_command()` for gateway/CLI slash commands;
- `llm_request` middleware;
- dashboard extension system;
- dashboard layout `<plugin>/dashboard/manifest.json`, `dist/index.js`, optional `plugin_api.py`;
- dashboard backend namespace `/api/plugins/<name>/`.

Hermes public APIs are authoritative over copied assumptions from other plugins.

## 5. License obligations

The three Jev integration projects inspected above are MIT-licensed. See `THIRD_PARTY_NOTICES.md`.

When code is copied or substantially adapted:

1. preserve the relevant copyright/license notice;
2. mention source file/repository and reference commit in comments or notice as appropriate;
3. update this document if the adopted scope changes.

Conceptual inspiration without code reuse should still be named here for transparency.
