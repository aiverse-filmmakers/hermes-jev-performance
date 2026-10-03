# Source of Truth

**Repository:** `aiverse-filmmakers/hermes-jev-performance`

This document defines the canonical product and engineering contract for Hermes Jev Performance. If implementation, issues, comments, or older documents conflict with this document, this document and the linked ADRs win until deliberately amended.

## 1. Product statement

Hermes Jev Performance is a Hermes-native plugin that uses Jev for fast bounded tool-routing decisions, then measures whether those decisions actually improve Hermes response time, tool usage, token usage, and cost.

The project must answer two separate questions:

1. **Did Jev make a fast routing decision?**
2. **Did using that decision improve the complete Hermes turn compared with normal Hermes behavior?**

Those are not the same metric and must never be conflated.

## 2. Non-negotiable invariants

1. Hermes remains the agent. Jev is advisory routing infrastructure, not the main reasoning model.
2. v1 does not replace the user's Hermes model, provider, or authentication path.
3. The plugin is Hermes-native. v1 does not insert a generic LLM proxy/gateway between Hermes and its provider.
4. Jev failure, timeout, malformed output, missing credentials, unsupported Hermes versions, or low confidence must fail open to normal Hermes behavior.
5. The plugin must support `off`, `shadow`, and `on` modes.
6. `off` must make zero Jev API calls while telemetry may continue collecting baseline Hermes metrics.
7. `shadow` may call Jev and record the decision but must not change Hermes' available tools.
8. `on` may restrict tools only when the route is valid and sufficiently confident.
9. A mixed or uncertain request must not be trapped in one tool family. `multi` and fallback paths leave Hermes unrestricted.
10. Mode changes must be possible from gateway chat slash commands, including Telegram, without SSH for normal operation.
11. Prompts, tool arguments, secrets, credentials, file contents, memory contents, and tool results must not be persisted in performance telemetry by default.
12. The dashboard must report unavailable metrics as unavailable, never synthesize token or timing values.
13. Organic ON vs OFF data is observational. Only controlled matched workloads may be labelled as an A/B benchmark.
14. No private installation-specific details belong in this public repository.

## 3. v1 scope

### Included

- OpenRouter Jev Decisions API support.
- Tool-family routing.
- Routing families: `github`, `apps`, `web`, `terminal`, `files`, `memory`, `skills`, `media`, `none`, `multi`.
- Persistent modes: off, shadow, on.
- Configurable confidence threshold and timeout.
- Fail-open behavior.
- Hermes slash commands and CLI/status controls.
- Optional per-reply Jev notice.
- Local metrics storage.
- Native Hermes web dashboard tab.
- Separately installable native Hermes Desktop dashboard using the selected authenticated backend/profile.
- Server only on a VPS, Desktop only on the user's computer, or both components on a local computer, from this one repository.
- Telegram/gateway status and control commands.
- Jev latency, confidence, cost, provider/model, route and error/skipped reason.
- Hermes turn duration, LLM request count, tool-call count, token metrics when Hermes exposes them reliably.
- Baseline comparison and controlled benchmark support.
- Packaging, doctor/self-check, migration, and uninstall path.

### Experimental compaction extension

The project now includes a separately configured, OFF-by-default Hermes `ContextEngine` named `hermes-jev-performance`. It applies Jev yes/no judgments to older large tool outputs, preserves recent exchanges and small/error outputs, writes exact outputs to profile-private storage before replacing them with references, and provides the `jev_recover` tool. SHADOW leaves the transcript unchanged; ON requires successful archive writes and otherwise falls back to normal Hermes compression. This extension remains experimental until live resume, provider, and lifecycle gates pass.

### Explicitly deferred

- Automatic primary-model/provider switching.
- Generic OpenAI/Anthropic proxy mode.
- Hosted telemetry.
- Fleet-wide centralized analytics.
- Memory reranking, web-injection screening, GUI control, browser control, mailbox triage, or policy gates from upstream projects.
- Automatic remote dashboard exposure.

These may become later modules only through an ADR and separate milestone.

## 4. Canonical documents

- [`PRD.md`](PRD.md): product requirements and acceptance criteria.
- [`INSTALL.md`](INSTALL.md): native Hermes install, upgrade, rollback, disable and uninstall lifecycle.
- [`COMPATIBILITY.md`](COMPATIBILITY.md): Hermes/Python compatibility matrix and live validation status.
- [`LIVE_RELEASE_GATE.md`](LIVE_RELEASE_GATE.md): batched real-environment P1-P9 acceptance procedure.
- [`ARCHITECTURE.md`](ARCHITECTURE.md): runtime design, modules, data flow, storage and interfaces.
- [`ROADMAP.md`](ROADMAP.md): phases, tasks, subtasks and gates.
- [`TELEMETRY.md`](TELEMETRY.md): metric definitions and storage contract.
- [`BENCHMARK.md`](BENCHMARK.md): controlled matched benchmark methodology, safety, execution and export.
- [`TESTING.md`](TESTING.md): test layers, fixtures and release gates.
- [`SECURITY.md`](SECURITY.md): privacy, credentials, dashboard exposure and threat boundaries.
- [`UPSTREAMS.md`](UPSTREAMS.md): upstream repositories, inspected snapshots and reuse plan.
- [`DECISIONS.md`](DECISIONS.md): architecture decision records.
- [`STATUS.md`](STATUS.md): live implementation status.
- [`API.md`](API.md): versioned authenticated backend API and safe error contract.
- [`INSTALLATION_PROGRESS.md`](INSTALLATION_PROGRESS.md): component delivery evidence and remaining live verification.

## 5. Definition of done for v1

v1 is done only when all of the following are true:

- Plugin installs without editing Hermes core.
- `hermes plugins doctor` or equivalent supported validation passes.
- OpenRouter Jev call works through the configured secret path.
- All routing families and `multi` have deterministic tests.
- Off/shadow/on behave exactly as defined.
- Telegram/gateway `/jev` control works.
- A Jev failure does not break a Hermes turn.
- Dashboard loads as a Hermes dashboard plugin.
- Native Desktop panel loads, follows the actual REST connection/profile, and rejects stale responses after switches.
- Dashboard can switch modes through authenticated/local Hermes dashboard APIs.
- Metrics contain no prompt/tool payloads by default.
- Baseline mode collects Hermes metrics without Jev calls.
- Controlled benchmark can compare matched workloads.
- At least one compatibility matrix run passes against the supported Hermes release range.
- Install, upgrade, disable, uninstall and rollback are documented and tested.
- Third-party notices are complete for any reused code.

## 6. Change protocol

Any change to an invariant, v1 scope, stored telemetry fields, credential behavior, routing taxonomy, or Hermes integration seam requires:

1. an ADR update or new ADR;
2. corresponding PRD/architecture changes;
3. test-plan changes;
4. status/roadmap updates;
5. explicit mention in the implementing PR.

## 7. Public-repository hygiene

Never commit:

- real API keys or key fragments;
- real usernames, user IDs, chat IDs, phone numbers, email addresses, hostnames, IPs or private URLs;
- private repository names;
- personal profile names;
- production logs containing user prompts or tool payloads;
- real filesystem paths that identify an individual installation;
- generated metrics copied from a private deployment unless intentionally anonymized and reviewed.

Use placeholders such as `<HERMES_HOME>`, `<PROFILE>`, `<TOKEN>`, `<HOST>` and synthetic benchmark data in documentation and tests.
