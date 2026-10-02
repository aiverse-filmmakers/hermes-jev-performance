# Implementation Roadmap

Every phase has an explicit gate. Do not start a later phase by silently bypassing a failed earlier gate. Small follow-up fixes may be made across previous phases when required.

## Phase 0 - Foundation and provenance

**Goal:** establish the public source of truth before code.

- [x] 0.1 Initialize repository.
- [x] 0.2 Define v1 scope and invariants.
- [x] 0.3 Define PRD.
- [x] 0.4 Define architecture.
- [x] 0.5 Record upstream projects and MIT notices.
- [x] 0.6 Define telemetry methodology.
- [x] 0.7 Define testing/security plans.
- [x] 0.8 Create live status tracker.

**Gate P0:** documentation PR reviewed/merged; no private installation details present.

## Phase 1 - Hermes plugin skeleton

**Goal:** a clean plugin that loads but does not yet call Jev.

- [x] 1.1 Create `plugin.yaml` with explicit manifest/version/license.
- [x] 1.2 Create minimal `register(ctx)` entry point.
- [x] 1.3 Add package/module layout.
- [x] 1.4 Add config validation and defaults.
- [x] 1.5 Add compatibility feature detection.
- [x] 1.6 Add `/jev status` with no secrets.
- [x] 1.7 Add unit tests for config and command parsing.
- [x] 1.8 Add CI lint/test workflow.

**Gate P1:** plugin doctor/import passes; `/jev status` works; no Jev network calls exist yet.

## Phase 2 - OpenRouter Jev client

**Goal:** isolated, tested Jev transport.

- [x] 2.1 Implement OpenRouter Decisions endpoint client.
- [x] 2.2 Implement configurable model ID.
- [x] 2.3 Implement dedicated credential lookup.
- [x] 2.4 Add optional generic OpenRouter credential compatibility path.
- [x] 2.5 Implement request timeout.
- [x] 2.6 Measure monotonic latency.
- [x] 2.7 Parse usage/cost safely.
- [x] 2.8 Normalize HTTP/provider/schema failures without leaking bodies/headers.
- [x] 2.9 Add mocked contract tests.
- [x] 2.10 Add optional explicit live smoke test command, never run implicitly in CI.

**Gate P2:** mocked client tests pass; explicit smoke test can return route answers and usage through OpenRouter.

## Phase 3 - Tool-family router

**Goal:** produce a valid conservative routing decision without modifying Hermes yet.

- [ ] 3.1 Define family criteria for 10 families.
- [ ] 3.2 Add `multi` criteria for mixed workflows.
- [ ] 3.3 Add confidence threshold validation.
- [ ] 3.4 Add family result parser.
- [ ] 3.5 Add per-turn decision cache keyed by Hermes turn context.
- [ ] 3.6 Add route validity checks.
- [ ] 3.7 Add tool-family registry.
- [ ] 3.8 Add unknown-tool and always-keep policy.
- [ ] 3.9 Add deterministic unit fixtures for each family.
- [ ] 3.10 Add ambiguous/mixed fixtures that must fall back safely.

**Gate P3:** classification suite passes and invalid/low-confidence/multi decisions never produce a hard filter.

## Phase 4 - Off / Shadow / On middleware

**Goal:** safely integrate routing into Hermes request flow.

- [ ] 4.1 Register `llm_request` middleware through public API.
- [ ] 4.2 Implement fresh-turn detection.
- [ ] 4.3 OFF: zero Jev calls, unchanged tools.
- [ ] 4.4 SHADOW: one Jev call, unchanged tools.
- [ ] 4.5 ON: one Jev call, accepted tool filtering.
- [ ] 4.6 Reuse decision across tool-loop provider calls.
- [ ] 4.7 Fail open on every Jev/plugin exception.
- [ ] 4.8 Preserve primary model/provider/auth settings.
- [ ] 4.9 Add integration tests with synthetic Hermes requests/tool schemas.
- [ ] 4.10 Add regression tests for mixed workflows.

**Gate P4:** all three modes behave exactly as specified; simulated failures never break the Hermes request.

## Phase 5 - Telegram/gateway and CLI controls

**Goal:** day-to-day control without SSH.

- [ ] 5.1 `/jev` status summary.
- [ ] 5.2 `/jev on`.
- [ ] 5.3 `/jev off`.
- [ ] 5.4 `/jev shadow`.
- [ ] 5.5 `/jev notice on|off`.
- [ ] 5.6 `/jev stats` concise recent/aggregate summary.
- [ ] 5.7 Persist settings across restart.
- [ ] 5.8 Ensure mode takes effect on next fresh turn without reinstall.
- [ ] 5.9 Add gateway command tests.
- [ ] 5.10 Add CLI equivalents where supported.

**Gate P5:** gateway command path toggles routing state and survives restart; no secret is printed.

## Phase 6 - Telemetry and local metrics store

**Goal:** capture accurate Jev and Hermes metadata independently from the dashboard.

- [ ] 6.1 Implement SQLite schema/migrations.
- [ ] 6.2 Record decision metadata.
- [ ] 6.3 Record turn lifecycle/duration.
- [ ] 6.4 Count LLM requests.
- [ ] 6.5 Count tool calls.
- [ ] 6.6 Capture provider token fields when supported.
- [ ] 6.7 Record routing skipped/fallback reasons.
- [ ] 6.8 Implement retention cleanup.
- [ ] 6.9 Implement aggregation queries.
- [ ] 6.10 Add telemetry redaction/no-content tests.
- [ ] 6.11 Verify DB failure does not break routing.

**Gate P6:** metrics tests prove no prompt/tool payload persistence and OFF/SHADOW/ON records are queryable.

## Phase 7 - Native Hermes dashboard

**Goal:** performance dashboard inside `hermes dashboard`.

- [ ] 7.1 Add dashboard manifest.
- [ ] 7.2 Add pre-built SDK UI bundle.
- [ ] 7.3 Add `plugin_api.py` FastAPI router.
- [ ] 7.4 Status/mode card.
- [ ] 7.5 Jev latency/confidence/cost cards.
- [ ] 7.6 Route distribution.
- [ ] 7.7 Hermes duration/tool-call/LLM-call/token charts.
- [ ] 7.8 Recent decisions table.
- [ ] 7.9 Skipped/fallback reason breakdown.
- [ ] 7.10 ON vs OFF/shadow comparison.
- [ ] 7.11 Mode toggle with read-back verification.
- [ ] 7.12 Responsive/mobile layout.
- [ ] 7.13 Dashboard API auth/security tests.

**Gate P7:** dashboard loads through Hermes plugin discovery, reflects real DB values, and mode toggles are verified.

## Phase 8 - Controlled A/B benchmark

**Goal:** distinguish actual causal benchmark results from ordinary usage correlations.

- [ ] 8.1 Define synthetic/mocked CI benchmark fixtures.
- [ ] 8.2 Define optional local read-only end-to-end benchmark suite.
- [ ] 8.3 Run matched workloads OFF then ON with warm-up rules.
- [ ] 8.4 Record environment/version metadata without personal identifiers.
- [ ] 8.5 Calculate duration/tool/LLM/token deltas.
- [ ] 8.6 Separate benchmark records from observational records.
- [ ] 8.7 Render benchmark results in dashboard.
- [ ] 8.8 Add export of anonymized benchmark JSON.

**Gate P8:** benchmark can be reproduced and does not make unsupported causal claims.

## Phase 9 - Hardening, packaging and migration

**Goal:** make the plugin safe to distribute.

- [ ] 9.1 Installer/update path.
- [ ] 9.2 Disable/uninstall/rollback path.
- [ ] 9.3 `doctor` diagnostics.
- [ ] 9.4 Schema migration tests.
- [ ] 9.5 Hermes compatibility matrix.
- [ ] 9.6 Timeout/provider outage tests.
- [ ] 9.7 Corrupt DB recovery/degraded mode.
- [ ] 9.8 Third-party notice audit.
- [ ] 9.9 Public-repo secret/private-data scan.
- [ ] 9.10 Documentation install/upgrade/uninstall walkthrough.

**Gate P9:** clean install and clean uninstall are repeatable on supported Hermes versions.

## Phase 10 - Public beta

**Goal:** publish a conservative beta with evidence.

- [ ] 10.1 Tag beta release.
- [ ] 10.2 Publish compatibility table.
- [ ] 10.3 Publish known limitations.
- [ ] 10.4 Publish measured benchmark methodology and results only where actually run.
- [ ] 10.5 Collect issue reports without telemetry upload.
- [ ] 10.6 Fix beta blockers.
- [ ] 10.7 Decide v1 stable gate.

**Gate P10:** no known data-loss/security blocker; no core Hermes patch; fail-open verified.

## Future milestones, not v1

- Optional model routing.
- Direct TypeSafe provider.
- Additional Jev providers.
- Adaptive mid-turn re-routing.
- Fleet dashboards.
- Optional upstream Jev skills such as memory filtering or web screening.

Each future milestone requires an ADR before implementation.
