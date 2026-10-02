"""Controlled OFF-vs-ON benchmark planning and comparison math."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import platform
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
import uuid

from . import __version__


BENCHMARK_VERSION = 1
DEFAULT_REPEATS = 3
DEFAULT_WARMUPS = 1
METRIC_FIELDS = (
    "hermes_duration_ms",
    "tool_calls",
    "llm_requests",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
)


@dataclass(frozen=True)
class BenchmarkFixture:
    fixture_id: str
    family: str
    prompt: str
    read_only: bool
    requires_network: bool = False
    validation_contains: str | None = None


@dataclass(frozen=True)
class PlannedSample:
    sample_id: str
    run_id: str
    fixture_id: str
    family: str
    mode: str
    repeat_index: int
    order_index: int
    is_warmup: bool


def _fixture_from_mapping(raw: Mapping[str, Any]) -> BenchmarkFixture:
    fixture_id = str(raw.get("id") or "").strip()
    family = str(raw.get("family") or "").strip()
    prompt = str(raw.get("prompt") or "").strip()
    if not fixture_id or not family or not prompt:
        raise ValueError("benchmark fixture requires id, family and prompt")
    if not bool(raw.get("read_only", False)):
        raise ValueError(f"benchmark fixture {fixture_id!r} is not declared read-only")
    validation = raw.get("validation_contains")
    if validation is not None:
        validation = str(validation)
    return BenchmarkFixture(
        fixture_id=fixture_id,
        family=family,
        prompt=prompt,
        read_only=True,
        requires_network=bool(raw.get("requires_network", False)),
        validation_contains=validation,
    )


def load_fixture_suite(
    path: Path | str,
    *,
    include_network: bool = False,
) -> list[BenchmarkFixture]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("fixtures") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError("benchmark fixture file must contain a fixtures array")
    fixtures = [_fixture_from_mapping(row) for row in rows if isinstance(row, Mapping)]
    fixtures = [
        fixture for fixture in fixtures
        if include_network or not fixture.requires_network
    ]
    if not fixtures:
        raise ValueError("benchmark fixture suite is empty")
    ids = [fixture.fixture_id for fixture in fixtures]
    if len(ids) != len(set(ids)):
        raise ValueError("benchmark fixture ids must be unique")
    return fixtures


def fixture_set_hash(fixtures: Sequence[BenchmarkFixture]) -> str:
    canonical = [
        {
            "id": fixture.fixture_id,
            "family": fixture.family,
            "prompt": fixture.prompt,
            "read_only": fixture.read_only,
            "requires_network": fixture.requires_network,
            "validation_contains": fixture.validation_contains,
        }
        for fixture in fixtures
    ]
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_plan(
    fixtures: Sequence[BenchmarkFixture],
    *,
    repeats: int = DEFAULT_REPEATS,
    warmups: int = DEFAULT_WARMUPS,
    run_id: str | None = None,
) -> list[PlannedSample]:
    if not fixtures:
        raise ValueError("at least one benchmark fixture is required")
    repeats = int(repeats)
    warmups = int(warmups)
    if repeats < 2 or repeats > 50:
        raise ValueError("repeats must be between 2 and 50")
    if warmups < 0 or warmups > 10:
        raise ValueError("warmups must be between 0 and 10")

    active_run_id = run_id or ("bench-" + uuid.uuid4().hex)
    result: list[PlannedSample] = []
    order_index = 0

    # Warm both paths consistently. Warm-ups are stored but excluded from comparison.
    for warmup_index in range(warmups):
        for fixture in fixtures:
            for mode in ("off", "on"):
                result.append(
                    PlannedSample(
                        sample_id="sample-" + uuid.uuid4().hex,
                        run_id=active_run_id,
                        fixture_id=fixture.fixture_id,
                        family=fixture.family,
                        mode=mode,
                        repeat_index=warmup_index,
                        order_index=order_index,
                        is_warmup=True,
                    )
                )
                order_index += 1

    # Pair the same fixture/repeat. Alternate mode order each repeat to reduce drift.
    for repeat_index in range(repeats):
        mode_order = ("off", "on") if repeat_index % 2 == 0 else ("on", "off")
        for fixture in fixtures:
            for mode in mode_order:
                result.append(
                    PlannedSample(
                        sample_id="sample-" + uuid.uuid4().hex,
                        run_id=active_run_id,
                        fixture_id=fixture.fixture_id,
                        family=fixture.family,
                        mode=mode,
                        repeat_index=repeat_index,
                        order_index=order_index,
                        is_warmup=False,
                    )
                )
                order_index += 1
    return result


def capture_environment(
    *,
    fixture_hash: str,
    repeats: int,
    warmups: int,
    provider: str,
    jev_model: str,
    hermes_version: str | None = None,
) -> dict[str, Any]:
    """Return deliberately low-cardinality environment metadata."""
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "plugin_version": __version__,
        "hermes_version": hermes_version,
        "python_version": platform.python_version(),
        "os_family": platform.system() or None,
        "architecture": platform.machine() or None,
        "provider": provider,
        "jev_model": jev_model,
        "fixture_set_sha256": fixture_hash,
        "repeats": int(repeats),
        "warmups": int(warmups),
        "order_policy": "paired_alternating",
        "python_implementation": platform.python_implementation(),
    }


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _sample_metric(sample: Mapping[str, Any], field: str) -> float | None:
    if field == "total_tokens":
        parts = [
            _number(sample.get("input_tokens")),
            _number(sample.get("output_tokens")),
        ]
        if all(value is None for value in parts):
            return None
        return sum(value or 0.0 for value in parts)
    return _number(sample.get(field))


def _delta(off_value: float | None, on_value: float | None) -> dict[str, float | None]:
    if off_value is None or on_value is None:
        return {
            "off_mean": off_value,
            "on_mean": on_value,
            "absolute_delta": None,
            "percent_change": None,
        }
    absolute = on_value - off_value
    percent = None if off_value == 0 else (absolute / off_value) * 100.0
    return {
        "off_mean": off_value,
        "on_mean": on_value,
        "absolute_delta": absolute,
        "percent_change": percent,
    }


def calculate_comparison(samples: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Calculate paired OFF-vs-ON deltas from successful measured samples only."""
    grouped: dict[tuple[str, int], dict[str, Mapping[str, Any]]] = {}
    success_counts = {"off": 0, "on": 0}
    measured_counts = {"off": 0, "on": 0}

    for sample in samples:
        if bool(sample.get("is_warmup")):
            continue
        mode = str(sample.get("mode") or "")
        if mode not in {"off", "on"}:
            continue
        measured_counts[mode] += 1
        if str(sample.get("status") or "") != "complete":
            continue
        success_counts[mode] += 1
        fixture_id = str(sample.get("fixture_id") or "")
        repeat_index = int(sample.get("repeat_index") or 0)
        grouped.setdefault((fixture_id, repeat_index), {})[mode] = sample

    pairs = [
        pair for pair in grouped.values()
        if "off" in pair and "on" in pair
    ]

    metrics: dict[str, Any] = {}
    for field in METRIC_FIELDS:
        off_values: list[float] = []
        on_values: list[float] = []
        paired_deltas: list[float] = []
        for pair in pairs:
            off_value = _sample_metric(pair["off"], field)
            on_value = _sample_metric(pair["on"], field)
            if off_value is None or on_value is None:
                continue
            off_values.append(off_value)
            on_values.append(on_value)
            paired_deltas.append(on_value - off_value)

        if not off_values:
            metrics[field] = {
                "pairs": 0,
                "off_mean": None,
                "on_mean": None,
                "absolute_delta": None,
                "percent_change": None,
                "paired_median_delta": None,
            }
            continue

        off_mean = statistics.fmean(off_values)
        on_mean = statistics.fmean(on_values)
        values = _delta(off_mean, on_mean)
        metrics[field] = {
            "pairs": len(off_values),
            **values,
            "paired_median_delta": statistics.median(paired_deltas),
        }

    return {
        "matched_pairs": len(pairs),
        "measured_samples": measured_counts,
        "successful_samples": success_counts,
        "success_rate": {
            mode: (
                success_counts[mode] / measured_counts[mode]
                if measured_counts[mode] else None
            )
            for mode in ("off", "on")
        },
        "metrics": metrics,
        "interpretation": "controlled_matched_benchmark",
        "claim_policy": (
            "Report absolute and percent deltas only. Do not call a result faster, "
            "cheaper, or better without reviewing sample count, failures, and methodology."
        ),
    }
