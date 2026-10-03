# Testing Strategy

## 1. Testing philosophy

The plugin sits on the agent request path, so correctness means more than "Jev returned a route." Tests must prove that routing is conservative, failures are harmless, telemetry is content-free, and disabling the plugin truly restores normal Hermes behavior.

## 2. Test layers

### Native compaction contract

Run the project tests, then test the context engine against the installed Hermes source in an isolated temporary profile:

```bash
python3 -m unittest discover -s tests -q
python3 scripts/verify_native_compaction.py --hermes-source /path/to/hermes-agent
python3 scripts/benchmark_compaction.py
```

The native contract covers engine discovery, per-agent cloning, multi-tool IDs, stale replay sidecars, archive recovery after a fresh engine instance, concurrent database appends, and OFF/SHADOW/provider-failure fallback. The benchmark is synthetic and offline by default; it reports exact-fact recall and recovery rather than claiming production accuracy.

### Unit tests

Cover pure modules without Hermes or network:

- config validation;
- mode parsing/persistence;
- family criteria;
- route parser;
- confidence threshold;
- tool registry/filter;
- `multi` behavior;
- error normalization;
- telemetry event construction;
- aggregation math;
- retention queries;
- slash-command parser.

### Contract tests

Mock OpenRouter Decisions responses:

- valid choice/confidence/usage;
- missing confidence;
- model alias/version changes;
- 400/401/402/429/500;
- timeout;
- malformed JSON;
- missing answers;
- unknown family;
- cost absent;
- usage absent.

### Hermes integration tests

Use synthetic request/tool schemas to verify:

- middleware returns unchanged request in OFF;
- SHADOW calls Jev but returns unchanged tools;
- ON filters accepted route;
- subsequent LLM calls reuse one turn decision;
- model/provider settings are unchanged;
- failure returns original request;
- family with zero matching tools returns original request;
- unknown tools follow configured safe policy.

### Dashboard tests

- manifest discovery;
- API status response;
- API aggregate queries;
- mode change + read-back;
- invalid mode rejected;
- dashboard never returns secrets/content;
- responsive smoke test where feasible.

### Gateway command tests

- `/jev`;
- `/jev status`;
- `/jev on|off|shadow`;
- `/jev notice on|off`;
- `/jev stats`;
- malformed command;
- state persists across plugin reload.

### Controlled benchmark tests

- deterministic synthetic OFF/ON fixtures with zero network calls;
- read-only local fixture validation;
- warm-up exclusion;
- paired alternating order;
- paired delta/percent math;
- incomplete half-pairs excluded;
- process-scoped benchmark mode override;
- user's persistent Jev mode remains unchanged;
- benchmark rows excluded from organic analytics;
- safe environment metadata only;
- anonymized export contains no sample IDs, paths, prompts or host identifiers;
- mocked live runner success and timeout/failure behavior;
- CLI preview performs zero live benchmark turns.

## 3. Routing fixture suite

At minimum include clear examples for:

1. github
2. apps
3. web
4. terminal
5. files
6. memory
7. skills
8. media
9. none
10. multi

Also include intentionally ambiguous prompts. The expected safe result may be `multi` or low-confidence fallback rather than forcing a family.

## 4. Mixed-workflow regression set

Required examples include requests conceptually equivalent to:

- public web research then local file output;
- GitHub inspection then web documentation research;
- app retrieval then local processing;
- local diagnostics then public error research;
- media analysis then file report.

These must never be hard-trapped by a single-family route unless the actual available tool architecture still permits all required steps.

## 5. Failure injection

Inject failures at every boundary:

- Jev DNS/connect timeout;
- provider 429;
- invalid credential;
- slow provider;
- corrupted response;
- SQLite locked/read-only;
- dashboard asset missing;
- dashboard API exception;
- missing Hermes context fields;
- unsupported Hermes API;
- telemetry hook exception.

Expected principle: **routing/observability may degrade; Hermes continues whenever Hermes itself can continue.**

## 6. Privacy tests

Automated tests should use marker secrets/content and assert they never appear in:

- SQLite rows;
- dashboard JSON;
- `/jev stats`;
- logs at normal verbosity;
- exception strings returned to the user.

## 7. Live smoke tests

Live paid tests are opt-in and separate from CI.

Minimum live smoke sequence:

1. plugin doctor/import;
2. explicit Jev API test;
3. one SHADOW request;
4. one ON clear-family request;
5. one OFF request;
6. verify no Jev API call in OFF;
7. verify dashboard row/aggregates;
8. verify `/jev` gateway control.

## 8. Compatibility matrix

For each supported Hermes release line:

- plugin discovery;
- middleware signature;
- turn context fields;
- command registration;
- telemetry hooks;
- dashboard plugin discovery/API;
- disable/uninstall behavior.

Unsupported versions must be documented rather than patched ad hoc.

## 9. Release gates

### Beta

- all unit/contract tests green;
- Hermes integration tests green;
- fail-open suite green;
- privacy tests green;
- one supported Hermes version live-smoked;
- dashboard functional;
- uninstall verified.

### Stable

- compatibility matrix across declared supported versions;
- benchmark methodology validated;
- no open P0/P1 security or data-loss issues;
- migrations tested from beta schema;
- third-party attribution audit complete.


## 10. Phase 9 hardening tests

Phase 9 additionally requires:

- native package layout and manifest version consistency;
- `requires_hermes` floor validation;
- no undeclared Python runtime dependency surface;
- non-network doctor diagnostics;
- doctor credential-presence checks that never return secret values;
- corrupt SQLite detection without automatic mutation;
- explicit corrupt-database quarantine/recreation;
- healthy database repair refusal;
- v1 -> v3 migration;
- v2 -> v3 migration;
- v3 migration idempotence;
- Hermes supported/degraded/unsupported feature-state fixtures;
- Jev timeout fail-open;
- provider 429 fail-open;
- provider 500 fail-open;
- unexpected provider exception fail-open;
- CI public-repository privacy/secret scan.

The P9 live lifecycle gate is manual by design: install, enable, disable, re-enable and remove must be exercised through Hermes' actual plugin lifecycle on a supported installation before public beta.

## 11. Batched live release gate

`scripts/live_release_gate.py` is the canonical P1-P9 real-environment runner.

Default execution is read-only on the active profile.

`--lifecycle --ref <FULL_COMMIT_SHA>` runs clean install, doctor, disable, re-enable, mode cycling and removal inside an isolated temporary `HERMES_HOME`.

`--live-jev` adds one explicit provider call. `--active-agent` adds real OFF/SHADOW/ON Hermes turns and restores the original mode.

The remaining Telegram and dashboard UI confirmations stay manual and must not be inferred from headless CI.

## Installation split correction checks

The `0.1.0-alpha.9` correction adds regression checks for actual REST/display profile agreement, delayed response/write read-back, unload cleanup, immutable package layout, archive persistence, strict API bodies, semantic manifest defaults, document links, and reproducible ZIPs.

Repository checks:

```sh
PYTHONPATH=agent python3 -m unittest discover -s tests -q
node --experimental-vm-modules --test tests/desktop.test.cjs
python3 scripts/sync_manifests.py --check
python3 scripts/build_release.py --output <TEMP_RELEASE_FOLDER>
python3 scripts/public_repo_scan.py .
```

Offline native checks, using the dependency runtime belonging to the inspected Hermes source (no installer is invoked):

```sh
<HERMES_PYTHON> scripts/verify_host_contracts.py --hermes-source <HERMES_SOURCE>
<HERMES_PYTHON> scripts/verify_native_compaction.py --hermes-source <HERMES_SOURCE>
```

Correction results: **240 Python unit/package tests, 11 Desktop behavior tests, 5 native loader/API/migration tests, and 6 native compaction tests**. Ruff 0.15.20 correctness checks (`E9,F`) also pass. The inspected host contracts use Hermes Agent source revision recorded in [HOST_CONTRACTS.md](HOST_CONTRACTS.md), with Python 3.11.16. JavaScript checks use Node 24.7.0 locally; CI uses Node 22.

The native loader test uses temporary extracted packages and synthetic profile data. It loads/unloads/reloads through the actual host manager and preserves saved modes, metrics, exact archived output, and an unrelated plugin. Its API test uses Hermes' actual mount/auth middleware and real FastAPI validation. These tests do not install into a real profile, exercise Git update provenance, prove actual Desktop reconciliation, or replace remote/VPS and visual app gates.
