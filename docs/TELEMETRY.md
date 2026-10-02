# Telemetry and Benchmarking

## 1. Principle

The dashboard must separate **Jev decision performance** from **Hermes end-to-end performance**.

A 300 ms Jev decision does not prove the Hermes turn became faster. Conversely, a slower individual turn does not prove Jev is harmful without a matched workload and enough samples.

## 2. Content policy

Persist metadata only. Do not persist:

- prompt text;
- tool arguments;
- tool results;
- file contents;
- memory content;
- API keys or headers;
- raw provider error bodies;
- private URLs.

## 3. Decision record

Current schema v2 table: `jev_decisions`.

| Field | Type | Meaning |
|---|---|---|
| id | integer | local row id |
| turn_key | text | opaque local correlation key |
| created_at | datetime | decision time |
| mode | text | off/shadow/on |
| provider | text | e.g. openrouter |
| requested_model | text nullable | requested Jev model identifier |\n| actual_model | text nullable | provider-returned Jev model identifier |
| family | text nullable | chosen route |
| confidence | real nullable | provider-returned confidence |
| latency_ms | real nullable | measured Jev request wall time |
| cost_usd | real nullable | provider-reported cost |
| input_tokens | integer nullable | provider-reported Jev input tokens |
| output_tokens | integer nullable | provider-reported Jev output tokens |
| accepted | boolean | route passed policy |
| applied | boolean | tool policy actually changed request |
| reason | text | applied/skipped/failure reason code |
| error_category | text nullable | normalized safe error category |\n| error_status_code | integer nullable | safe HTTP status when available |

No state/prompt column exists.

## 4. Turn record

Current schema v2 table: `hermes_turns`.

| Field | Type | Meaning |
|---|---|---|
| id | integer | local row id |
| turn_key | text | opaque correlation key |
| started_at | datetime | first observed turn time |
| completed_at | datetime nullable | final observed completion |
| mode | text | mode at turn start |
| route_family | text nullable | selected family |
| route_applied | boolean | whether filtering applied |\n| route_reason | text nullable | filtered/shadow/mode_off/fallback reason code |
| duration_ms | real nullable | end-to-end observed turn duration |
| llm_requests | integer | provider/LLM requests in turn |
| tool_calls | integer | tool calls in turn |
| input_tokens | integer nullable | provider-reported aggregate |
| cached_input_tokens | integer nullable | provider-reported aggregate |
| output_tokens | integer nullable | provider-reported aggregate |
| reasoning_tokens | integer nullable | provider-reported aggregate |
| status | text | complete/aborted/error/unknown |
| benchmark_run_id | text nullable | controlled benchmark grouping only |

Again, no prompt or tool payload fields.

## 5. Settings/audit record

Mode changes are auditable locally in the `mode_changes` table with metadata only:

```text
timestamp
old_mode
new_mode
source: command | dashboard | cli | config
```

No chat ID or user identity is stored for v1 metrics. `turn_key` is generated from Hermes correlation IDs with SHA-256 and only a shortened opaque digest is persisted.

## 5.1 Storage location\n\nBy default, metrics live under the active Hermes profile at:\n\n```text\n$HERMES_HOME/plugin-data/hermes-jev-performance/metrics.sqlite3\n```\n\nThe database uses versioned migrations. Schema v2 is the current Phase 6 schema. A database with a newer unknown schema fails closed for telemetry only; Hermes routing remains independent.\n\n## 6. Core calculations

### Jev latency

- p50
- p95
- mean
- maximum
- timeout rate

### Routing quality proxy metrics

- decisions by family;
- confidence distribution;
- accepted percentage;
- applied percentage;
- `multi` percentage;
- low-confidence fallback percentage;
- error/fail-open percentage;
- zero-tool fallback percentage.

These are operational metrics, not proof of semantic accuracy.

### Hermes outcome metrics

Per mode:

- mean/median turn duration;
- mean/median tool calls;
- mean/median LLM requests;
- input/output/cache/reasoning tokens when available;
- completion/error rate where observable.

## 7. Observational comparison

Dashboard may compare ordinary OFF, SHADOW and ON usage, but must label it **observational** because requests differ.

Recommended wording:

> Observational usage comparison. Workloads are not matched, so differences are not necessarily caused by Jev.

## 8. Controlled A/B benchmark

A controlled benchmark uses matched tasks under defined conditions.

Minimum methodology:

1. Pin Hermes/plugin/Jev model versions.
2. Record benchmark environment metadata without private host identifiers.
3. Warm required caches consistently or explicitly test cold vs warm separately.
4. Run the same safe workload set under OFF and ON.
5. Randomize or alternate order where practical to reduce time-of-day/provider drift.
6. Repeat enough times to avoid treating one run as a conclusion.
7. Store benchmark results with a `benchmark_run_id`.
8. Report absolute values and deltas.
9. Do not merge benchmark and organic usage statistics.

## 9. Benchmark safety

CI uses mocks/fixtures, never paid live APIs.

Optional real benchmark tasks must be read-only or use disposable fixtures by default. No benchmark should send email, alter GitHub, modify production files, purchase anything, or perform irreversible external actions.

## 10. Performance deltas

For metric M:

```text
absolute_delta = ON - OFF
percent_change = ((ON - OFF) / OFF) * 100
```

For duration/tokens/tool calls, negative percentage generally means less resource/time. UI wording must avoid calling a result "faster" if the sample/methodology does not justify it.

## 11. Cost

Jev cost should come from provider-returned usage when available. If unavailable, display `unavailable` by default. A price-table estimate may be a future optional feature but must be explicitly labelled estimated.

## 12. Retention

Default target: 30 days, configurable.

Retention cleanup deletes old metrics locally and is throttled to run at most once per hour per active profile during normal telemetry collection. A manual clear operation must require explicit user action in CLI/dashboard and must not touch Hermes conversation history.
