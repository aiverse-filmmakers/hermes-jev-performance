# Controlled Benchmark Methodology

Phase 8 adds a reproducible, explicit OFF-vs-ON benchmark. It is deliberately separate from ordinary Hermes usage analytics.

## What the benchmark answers

The benchmark compares the same read-only workload under:

- **OFF**: no Jev call and no tool filtering.
- **ON**: Jev may apply a confident tool-family route.

It measures:

- Hermes end-to-end turn duration;
- tool calls;
- LLM/provider requests;
- input tokens;
- cached input tokens;
- output tokens;
- reasoning tokens;
- total input + output tokens;
- Jev decision latency, confidence and provider-reported cost for ON samples.

It does not score answer quality automatically.

## Safety

The live benchmark is never run implicitly.

Preview only:

```bash
hermes jev benchmark
```

Explicit execution:

```bash
hermes jev benchmark --live
```

The default workload fixtures are read-only and exclude the public-web fixture. A live benchmark still uses the normal Hermes model/provider, and ON samples also call OpenRouter Jev. The optional public-web workload fixture requires:

```bash
hermes jev benchmark --live --include-network
```

The runner never changes the user's persistent Jev mode. Each spawned benchmark process receives a process-scoped OFF or ON override together with random benchmark correlation IDs.

## Default methodology

Defaults:

```text
fixtures: 4 local/read-only workload fixtures
warmups: 1 per fixture per mode
measured repeats: 3
modes: OFF and ON
order: paired alternating
public-web workload fixture: excluded
```

That produces:

```text
8 warm-up turns
24 measured turns
32 total Hermes turns
```

For repeat 0 the measured order is OFF then ON. Repeat 1 reverses to ON then OFF. Repeat 2 returns to OFF then ON. This reduces simple time/provider-order drift while preserving matched fixture/repeat pairs.

Warm-up samples are stored for auditability but excluded from comparison deltas.

## Local fixtures

Default read-only fixtures cover:

- `none`: simple no-tool control;
- `terminal`: read-only Python version command;
- `files`: read the repository README heading without modification;
- `skills`: inspect skill availability without modification.

Optional network fixture:

- `web`: public read-only lookup of the official Hermes Agent repository.

The default suite does not send email, modify GitHub, write production files, edit skills, alter memory, purchase anything, or invoke connected app mutations.

## Deltas

Only successful matched OFF/ON samples with the same:

```text
fixture_id + repeat_index
```

are used for metric deltas.

For each metric:

```text
absolute_delta = ON mean - OFF mean
percent_change = ((ON mean - OFF mean) / OFF mean) * 100
```

Negative duration/tool/token change means ON used less of that metric. Positive means more.

The dashboard intentionally says **change**, not **improvement**, because the benchmark does not automatically judge answer quality.

## Environment metadata

Each run records only low-cardinality reproducibility metadata:

- benchmark schema/version;
- plugin version;
- sanitized Hermes version;
- Python version and implementation;
- OS family;
- CPU architecture string;
- Jev provider/model;
- actual Hermes primary provider/model/API mode per sample when exposed by the successful main-loop hook;
- fixture-set SHA-256;
- repeat/warm-up counts;
- order policy.

It does not record hostname, username, home directory, current working directory, IP address, MAC address, API keys, prompts, tool payloads, raw Hermes turn IDs, or conversation content.

## Storage separation

Schema v3 introduced the dedicated benchmark tables; schema v4 adds the actual Hermes runtime provider/model/API-mode metadata captured per sample:

- `benchmark_runs`;
- `benchmark_samples`.

Each measured sample can additionally record the first successful main-loop Hermes provider, requested model, provider-returned response model, and API mode. This comes from Hermes observer-hook metadata, not from private config parsing.

Benchmark Hermes turns are tagged with random benchmark run/sample IDs and public fixture IDs.

All ordinary dashboard queries explicitly exclude benchmark-tagged Hermes turns and their Jev decisions. This prevents controlled benchmark data from silently affecting organic OFF/SHADOW/ON analytics.

## Synthetic CI benchmark

CI never calls Hermes providers or OpenRouter.

`benchmarks/fixtures/ci_synthetic.json` contains deterministic mocked OFF and ON metrics. Unit tests run the same pairing/delta engine against these fixtures and assert zero external calls.

## Export

A completed run can be exported from the dashboard or CLI.

CLI:

```bash
hermes jev benchmark --live --export ./benchmark.json
```

The JSON export includes:

- safe run metadata;
- methodology;
- paired comparison results;
- content-free sample metrics.

It excludes:

- benchmark sample IDs;
- raw Hermes turn IDs;
- prompts;
- tool arguments/results;
- filesystem paths;
- undeclared environment fields;
- host identifiers.

## Useful options

```bash
hermes jev benchmark --repeats 5 --warmups 1
hermes jev benchmark --live --repeats 5 --warmups 1
hermes jev benchmark --live --include-network
hermes jev benchmark --live --timeout 240
hermes jev benchmark --live --export ./benchmark.json
```

A preview without `--live` always performs zero benchmark turns.

## Interpretation

A controlled matched benchmark supports a stronger comparison than ordinary usage because the workloads are matched and warm-up/order rules are defined.

It still does not prove semantic equivalence or answer quality. Published claims must include sample count, fixture set, versions, failures, and methodology alongside any duration/token/tool delta.
