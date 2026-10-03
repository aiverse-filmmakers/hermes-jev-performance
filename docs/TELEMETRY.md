# Telemetry and Benchmarking

## 1. Principle

The dashboard must separate **Jev decision performance** from **Hermes end-to-end performance**.

A fast Jev decision does not prove the complete Hermes turn became faster. Ordinary ON/OFF usage also does not prove causality because the requests differ. Controlled matched benchmark data is therefore stored and rendered separately.

## 2. Content policy

Persist metadata only. Do not persist:

- prompt text;
- tool arguments;
- tool results;
- file contents;
- memory content;
- API keys or headers;
- raw provider error bodies;
- private URLs;
- raw Hermes session or turn IDs.

## 3. Decision record

Current observational decision table: `jev_decisions`.

| Field | Type | Meaning |
|---|---|---|
| id | integer | local row id |
| turn_key | text | opaque local correlation key |
| created_at | real | decision time |
| mode | text | shadow/on for Jev decisions |
| provider | text nullable | e.g. openrouter |
| requested_model | text nullable | requested Jev model |
| actual_model | text nullable | provider-returned Jev model |
| family | text nullable | chosen route |
| confidence | real nullable | provider-returned confidence |
| latency_ms | real nullable | measured Jev request wall time |
| cost_usd | real nullable | provider-reported cost |
| input_tokens | integer nullable | provider-reported Jev input tokens |
| output_tokens | integer nullable | provider-reported Jev output tokens |
| accepted | boolean | route passed policy |
| applied | boolean | eager tool policy actually changed request |
| reason | text | applied/skipped/failure reason |
| error_category | text nullable | normalized safe error |
| error_status_code | integer nullable | safe HTTP status |

No state/prompt column exists.

## 4. Hermes turn record

Current schema v4 table: `hermes_turns`.

| Field | Type | Meaning |
|---|---|---|
| turn_key | text | opaque SHA-256-derived local correlation key |
| started_at | real | first observed turn time |
| completed_at | real nullable | completion time |
| mode | text | effective mode for this process/turn |
| route_family | text nullable | selected family |
| route_applied | boolean | whether eager filtering applied |
| route_reason | text nullable | filtered/shadow/mode_off/fallback reason |
| duration_ms | real nullable | end-to-end observed turn duration |
| llm_requests | integer | provider/LLM requests |
| tool_calls | integer | tool calls |
| input_tokens | integer nullable | provider-reported aggregate |
| cached_input_tokens | integer nullable | provider-reported aggregate |
| output_tokens | integer nullable | provider-reported aggregate |
| reasoning_tokens | integer nullable | provider-reported aggregate |
| status | text | running/complete/interrupted/error/unknown |
| benchmark_run_id | text nullable | random controlled-benchmark run correlation |
| benchmark_sample_id | text nullable | random controlled-benchmark sample correlation |
| benchmark_fixture_id | text nullable | public fixture identifier |
| benchmark_warmup | boolean | whether sample is warm-up only |
| provider | text nullable | first successful main-loop Hermes provider |
| requested_model | text nullable | requested Hermes model from the successful provider hook |
| response_model | text nullable | provider-returned response model when available |
| api_mode | text nullable | Hermes provider API mode |

Benchmark tags contain identifiers only. They do not contain prompt text.

Reduced current-Hermes session-end hooks that omit `turn_id` are handled through a bounded in-memory session-to-opaque-turn map. Raw session IDs from that fallback are never written to SQLite.

## 5. Mode changes

`mode_changes` stores local metadata:

```text
timestamp
old_mode
new_mode
source: slash | dashboard | cli | config
```

The Phase 8 live benchmark uses a process-scoped mode override and therefore does not mutate the user's persistent mode.

## 6. Storage location and migrations

By default:

```text
$HERMES_HOME/plugin-data/hermes-jev-performance/metrics.sqlite3
```

Current schema version: **4**.

Migration path:

```text
v1 -> v2 -> v3 -> v4
```

A database with a newer unknown schema fails closed for telemetry only; Hermes routing remains independent.

## 7. Organic metrics

Organic dashboard queries explicitly exclude rows where `benchmark_run_id IS NOT NULL`.

This applies to:

- summary totals;
- route distribution;
- recent Jev decisions;
- fallback reasons;
- OFF/SHADOW/ON observational comparison;
- Hermes time-series data.

Controlled benchmark activity must never silently change ordinary usage charts.

## 8. Core calculations

### Jev operational metrics

Implemented aggregate fields include:

- average latency;
- p50 latency;
- p95 latency;
- confidence;
- provider-reported average cost when available;
- provider-reported total cost when available;
- decisions by family;
- accepted/applied percentage;
- multi/low-confidence/error/fail-open reasons through decision/turn metadata.

These are operational metrics, not semantic-accuracy proof.

Missing provider usage/cost metadata remains unavailable and does not invalidate an otherwise valid Jev decision.

### Hermes outcomes

Per mode or controlled sample:

- turn duration;
- tool calls;
- LLM requests;
- input/output/cache/reasoning tokens when available;
- completion/error state.

Missing values remain unavailable and are never estimated.

## 9. Observational comparison

Ordinary OFF, SHADOW and ON usage may be compared, but must be labelled observational:

> Observational usage comparison. Workloads are not matched, so differences are not necessarily caused by Jev.

## 10. Controlled benchmark schema

Schema v3 adds `benchmark_runs` and `benchmark_samples`. Schema v4 adds content-free Hermes runtime identity fields so the local benchmark database can record the actual primary provider/requested model/response model/API mode observed from successful main-loop hooks.

### benchmark_runs

Stores only reproducibility metadata:

- random run ID;
- created/completed timestamps;
- run status;
- benchmark version;
- fixture-set SHA-256;
- fixture count;
- repeat/warm-up counts;
- safe environment JSON;
- methodology JSON.

### benchmark_samples

Stores only metadata/results:

- random sample ID;
- run ID;
- public fixture ID/family;
- OFF/ON mode;
- repeat/order index;
- warm-up flag;
- status;
- runner duration;
- exit code and validation flag;
- Hermes duration;
- tool/LLM counts;
- token fields;
- local primary Hermes runtime identity fields;
- route family/applied flag;
- Jev latency/cost/confidence;
- normalized error category.

No prompt or tool payload fields exist.

## 11. Controlled A/B methodology

Minimum methodology implemented in Phase 8:

1. Pin plugin/Hermes/Jev version metadata.
2. Hash the exact fixture set.
3. Use read-only fixtures by default.
4. Warm OFF and ON consistently.
5. Exclude warm-ups from deltas.
6. Pair samples by `fixture_id + repeat_index`.
7. Alternate order between OFF→ON and ON→OFF on subsequent repeats.
8. Require at least two measured repeats.
9. Store benchmark records separately.
10. Require ON samples to prove the expected route behavior before they count as matched evidence.
11. Report absolute values and deltas.
12. Do not automatically turn lower resource use into a quality verdict.

A normal single-family ON fixture is valid only when the recorded family matches the fixture and filtering was applied. `none`/`multi` fixtures are valid only when the matching unrestricted route is recorded without a hard filter. Wrong-route or fail-open ON turns are tracked as invalid-routing samples and excluded from deltas.

Full reproducibility instructions are in [BENCHMARK.md](BENCHMARK.md).

## 12. Performance deltas

For metric M:

```text
absolute_delta = ON mean - OFF mean
percent_change = ((ON mean - OFF mean) / OFF mean) * 100
```

Warm-ups, incomplete pairs, and routing-invalid ON samples are excluded.

Negative duration/tool/token percentage means ON used less of that metric. It must not automatically be described as "better" without considering failures and result quality.

## 13. Synthetic CI benchmark

CI uses `benchmarks/fixtures/ci_synthetic.json`.

It:

- makes zero Hermes/provider/OpenRouter calls;
- exercises the same planning, routing-validity, pairing and delta engine;
- provides deterministic OFF/ON values;
- verifies warm-up exclusion and comparison math.

## 14. Live benchmark safety

Live execution is explicit:

```bash
hermes jev benchmark --live
```

Without `--live`, the CLI only prints the benchmark plan.

Before any live turn, the runner validates telemetry availability, OpenRouter v1 provider/credential availability, timeout bounds, fixtures and plan construction.

The live runner:

- uses process-scoped OFF/ON overrides;
- leaves the user's persistent Jev mode unchanged;
- defaults to local/read-only workload fixtures while still using the configured Hermes model and Jev provider;
- requires `--include-network` for the public-web fixture;
- never performs app/email/GitHub mutation fixtures by default;
- marks a run `complete_with_failures` when a measured sample is incomplete or an ON sample does not produce the expected routing behavior.

## 15. Dashboard and export privacy

Authenticated dashboard benchmark history exposes reviewed low-cardinality environment/methodology fields and aggregate comparison results. It deliberately does not expose arbitrary local primary provider/model/API strings because custom values may contain private deployment identifiers or filesystem paths.

An anonymized JSON export contains explicitly whitelisted safe environment/methodology metadata, comparison results and content-free sample metrics.

It excludes:

- prompts;
- tool payloads;
- sample IDs;
- raw Hermes turn IDs;
- filesystem paths;
- host/user identifiers;
- undeclared environment values;
- undeclared methodology values;
- arbitrary local primary provider/model/API-mode strings.

## 16. Cost

Jev cost comes from provider-returned usage when available. Missing cost is displayed as unavailable.

The live benchmark can also incur the user's normal Hermes primary-model/provider usage. That is why execution requires the explicit `--live` flag.

## 17. Retention

Default target: 30 days, configurable.

Retention cleanup deletes old organic telemetry and benchmark records locally. It preserves an old benchmark-run row while any retained newer sample still references that run, preventing orphaned benchmark samples.

Cleanup runs at most once per hour per active profile during normal collection.

Deleting metrics must never touch Hermes conversation history.
