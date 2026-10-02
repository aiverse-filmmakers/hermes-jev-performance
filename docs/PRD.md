# Product Requirements Document

## 1. Problem

Jev can make a fast tool-routing decision, but users need proof that adding Jev to Hermes improves the complete agent workflow. A routing integration without observability makes it impossible to know whether Jev reduces response time, tool calls, token usage, or cost, or simply adds latency.

Hermes Jev Performance therefore combines conservative Jev tool routing with first-class measurement and an explicit baseline mode.

## 2. Primary user

A Hermes user who normally interacts through a messaging gateway such as Telegram and wants:

- normal Hermes behavior by default;
- one-command Jev enable/disable/shadow control;
- no dependency on SSH for day-to-day switching;
- a browser dashboard for deeper performance inspection;
- evidence that Jev is helping rather than a marketing claim.

## 3. Goals

- Reduce unnecessary tool exposure when a request clearly belongs to one tool family.
- Make Jev's own latency/cost visible.
- Measure whole-turn Hermes outcomes.
- Provide honest ON vs OFF comparison.
- Preserve Hermes capability and authentication.
- Keep operation safe, reversible and low-maintenance.

## 4. Non-goals

- Selecting a different primary LLM in v1.
- Replacing Hermes provider auth.
- Implementing a generic provider proxy.
- Logging content for analytics.
- Making performance claims from unmatched workloads.

## 5. Functional requirements

### FR-001 Hermes-native installation

The project MUST install as a Hermes plugin using public plugin APIs and MUST NOT patch Hermes core files.

### FR-002 OpenRouter Jev backend

The plugin MUST support OpenRouter's Jev Decisions endpoint and a versioned Jev model ID. The model ID MUST be configurable. The initial default is `typesafe/jev-1.13` unless upstream availability requires a documented change.

### FR-003 Credential handling

The plugin MUST prefer a dedicated Jev/OpenRouter credential name and MAY support an explicitly documented compatibility path for an existing generic OpenRouter credential. Secrets MUST never be written to telemetry or returned by status commands.

### FR-004 Modes

The plugin MUST implement:

- `off`: no Jev call, no routing modification;
- `shadow`: Jev decides and metrics are recorded, but tools are not modified;
- `on`: Jev decides and may apply the route when accepted.

Mode MUST persist across process restart and MUST be changeable without reinstalling the plugin.

### FR-005 Fresh-turn routing

By default, the plugin MUST make at most one tool-family Jev routing request per fresh user turn. Tool-loop LLM calls MUST reuse the accepted turn route rather than repeatedly billing Jev.

### FR-006 Routing taxonomy

v1 MUST support these semantic routes:

- `github`: GitHub repository, pull request, issue, Actions, commit, branch and related GitHub work;
- `apps`: connected external services and deferred app/MCP tools;
- `web`: public web search/extraction/browser research;
- `terminal`: shell, process, service, package, VPS/system and command execution work;
- `files`: local file read/search/write/patch operations;
- `memory`: Hermes memory retrieval/operations;
- `skills`: skill discovery/view/manage operations;
- `media`: vision, TTS and other media-specific agent tools included by policy;
- `none`: request should normally need no tool;
- `multi`: request clearly spans multiple tool families or should remain unrestricted.

### FR-007 Tool-policy registry

Tool-to-family mapping MUST be data-driven/configurable rather than scattered through middleware code. Unknown tools MUST default to safe availability rather than accidental removal unless the policy explicitly says otherwise.

### FR-008 Conservative application

A route MUST NOT be applied when:

- confidence is below threshold;
- Jev returns an unknown/invalid family;
- the family maps to zero usable tools;
- the route is `multi`;
- the plugin cannot safely identify the fresh turn;
- required Hermes context is missing;
- Jev times out or errors.

Those conditions MUST fail open.

### FR-009 Preserve Hermes identity/auth

Routing MUST NOT switch Hermes' primary model/provider in v1 and MUST NOT replace existing provider authentication.

### FR-010 Gateway slash commands

The plugin MUST expose a `/jev` command compatible with Hermes messaging gateways. Required subcommands:

```text
/jev
/jev status
/jev on
/jev off
/jev shadow
/jev notice on
/jev notice off
/jev stats
```

### FR-011 Optional reply notice

When notice mode is on, a routed reply MAY include a concise routing footer/status such as family, confidence and Jev latency. Notice mode MUST default to off.

### FR-012 CLI controls

Where supported by Hermes public APIs, equivalent CLI status/configuration controls MUST be provided for headless administration and diagnostics.

### FR-013 Decision telemetry

For every Jev decision, store only metadata required for performance analysis, including route, confidence, latency, provider/model identifier, cost when returned, mode, accepted/applied state, and failure/skipped reason.

### FR-014 Turn telemetry

For every observed Hermes turn, record metadata available from supported Hermes seams, including total turn duration, LLM request count, tool-call count, and provider-reported token fields where available.

### FR-015 Local persistence

Telemetry MUST be stored locally by default. SQLite is the v1 persistence target. Retention MUST be configurable.

### FR-016 Native Hermes dashboard

The plugin MUST ship a Hermes dashboard extension under the supported plugin dashboard layout, with a backend API under Hermes' plugin API namespace.

### FR-017 Dashboard controls

The dashboard MUST show current mode and allow switching among off/shadow/on through the authenticated/local Hermes dashboard backend.

### FR-018 Dashboard metrics

The dashboard MUST expose:

- current Jev status;
- decisions count;
- route distribution;
- Jev latency p50/p95;
- average confidence;
- Jev cost totals/averages when available;
- turn duration;
- tool calls per turn;
- LLM calls per turn;
- token fields when available;
- recent decision table;
- reasons routing was skipped/not applied;
- ON vs OFF/shadow comparisons with clear labels.

### FR-019 Baseline mode

`off` MUST continue recording non-Jev Hermes performance metadata where technically available, creating a true baseline without Jev API calls.

### FR-020 Controlled benchmark

The project MUST provide an optional safe benchmark harness capable of running matched workloads under OFF and ON. Results MUST be labelled controlled benchmark data and MUST be kept separate from ordinary observational usage.

### FR-021 Doctor/self-check

The project MUST provide a non-destructive diagnostic path that checks plugin loading, required APIs, configuration, database writability, dashboard assets and credential presence without printing secrets.

### FR-022 Disable/uninstall

Disabling or uninstalling the plugin MUST restore normal Hermes operation without requiring Hermes core rollback.

## 6. Non-functional requirements

### NFR-001 Fail-open reliability

No Jev-specific exception may escape into the Hermes turn path when normal Hermes can continue.

### NFR-002 Low overhead

Target Jev decision latency is p50 under 750 ms and p95 under 2 s under normal provider conditions. These are engineering targets, not guarantees. A configurable hard timeout MUST cap added latency.

### NFR-003 No content telemetry

Performance storage MUST NOT contain prompt text, file contents, tool arguments, tool results, memory contents, or credentials by default.

### NFR-004 Honest metrics

Missing metrics are `null`/unavailable. They MUST NOT be estimated unless explicitly labelled as an estimate in a separate experimental feature.

### NFR-005 Backward tolerance

Unsupported Hermes versions MUST degrade safely, with a clear compatibility/status message rather than silently patching internals.

### NFR-006 Minimal dependencies

Prefer Python standard library and Hermes-bundled dependencies. New runtime dependencies require justification in an ADR.

### NFR-007 Local dashboard security

Dashboard APIs MUST rely on Hermes' dashboard authentication model and MUST NOT create an unauthenticated public listener.

### NFR-008 Reproducible provenance

Copied/adapted upstream code MUST be traceable to repository and reference commit in `UPSTREAMS.md` and retain required MIT notices.

## 7. Success metrics

v1 success means the software can measure, not assume, whether Jev helps. A deployment should be able to answer:

- What is Jev's p50/p95 routing latency?
- What does Jev cost per decision and over a selected period?
- What percentage of turns are routed, shadowed, skipped, multi, low-confidence or failed-open?
- How do matched OFF vs ON benchmark workloads compare in total duration, tool calls, LLM calls and available token fields?
- Can the user disable Jev from their messaging gateway and immediately return to normal Hermes behavior?

## 8. Release acceptance

No v1 release until every P0/P1 requirement has a test or documented manual verification and all gates in `ROADMAP.md` are green.
