"""Anonymized benchmark export helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .benchmark import calculate_comparison
from .store import MetricsStore


_ENVIRONMENT_KEYS = {
    "benchmark_version",
    "plugin_version",
    "hermes_version",
    "python_version",
    "os_family",
    "architecture",
    "provider",
    "jev_model",
    "fixture_set_sha256",
    "repeats",
    "warmups",
    "order_policy",
    "python_implementation",
}

_SAMPLE_KEYS = {
    "fixture_id",
    "family",
    "mode",
    "repeat_index",
    "order_index",
    "is_warmup",
    "status",
    "runner_duration_ms",
    "exit_code",
    "validation_passed",
    "hermes_duration_ms",
    "llm_requests",
    "tool_calls",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "hermes_provider",
    "hermes_requested_model",
    "hermes_response_model",
    "hermes_api_mode",
    "route_family",
    "route_applied",
    "jev_latency_ms",
    "jev_cost_usd",
    "jev_confidence",
    "error_category",
}


def _pick(mapping: dict[str, Any], keys: set[str]) -> dict[str, Any]:
    return {key: mapping.get(key) for key in sorted(keys) if key in mapping}


def build_anonymized_export(store: MetricsStore, run_id: str) -> dict[str, Any]:
    run = store.benchmark_run_record(run_id)
    if run is None:
        raise KeyError("benchmark run not found")
    samples = store.benchmark_samples(run_id, include_warmups=True)

    environment = run.get("environment")
    safe_environment = _pick(
        environment if isinstance(environment, dict) else {},
        _ENVIRONMENT_KEYS,
    )
    methodology = run.get("methodology")
    safe_methodology = dict(methodology) if isinstance(methodology, dict) else {}

    return {
        "format": "hermes-jev-performance-benchmark-v1",
        "run": {
            "run_id": run["run_id"],
            "status": run["status"],
            "benchmark_version": run["benchmark_version"],
            "fixture_set_hash": run["fixture_set_hash"],
            "fixture_count": run["fixture_count"],
            "repeats": run["repeats"],
            "warmups": run["warmups"],
            "environment": safe_environment,
            "methodology": safe_methodology,
        },
        "comparison": calculate_comparison(samples),
        "samples": [
            _pick(sample, _SAMPLE_KEYS)
            for sample in samples
        ],
        "privacy": {
            "prompt_text_included": False,
            "tool_payloads_included": False,
            "raw_turn_ids_included": False,
            "filesystem_paths_included": False,
            "host_identifiers_included": False,
        },
    }


def write_anonymized_export(
    store: MetricsStore,
    run_id: str,
    path: Path | str,
) -> Path:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = build_anonymized_export(store, run_id)
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target
