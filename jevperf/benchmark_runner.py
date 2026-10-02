"""Explicit opt-in local Hermes OFF-vs-ON benchmark runner."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any

from .benchmark import (
    BENCHMARK_VERSION,
    DEFAULT_REPEATS,
    DEFAULT_WARMUPS,
    build_plan,
    calculate_comparison,
    capture_environment,
    fixture_set_hash,
    load_fixture_suite,
)
from .benchmark_context import BenchmarkContext, benchmark_env
from .config import read_config
from .store import MetricsStore, default_db_path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE_PATH = PLUGIN_ROOT / "benchmarks" / "fixtures" / "readonly_local.json"
_VERSION_RE = re.compile(r"Hermes Agent v([A-Za-z0-9.+_-]+)")


def detect_hermes_version(executable: str) -> str | None:
    try:
        completed = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return None
    text = (completed.stdout or "") + "\n" + (completed.stderr or "")
    match = _VERSION_RE.search(text)
    return match.group(1) if match else None


def _safe_error_category(exc: BaseException) -> str:
    if isinstance(exc, subprocess.TimeoutExpired):
        return "timeout"
    if isinstance(exc, FileNotFoundError):
        return "hermes_not_found"
    if isinstance(exc, PermissionError):
        return "permission_error"
    if isinstance(exc, OSError):
        return "process_os_error"
    return "runner_error"


def _store_from_telemetry(telemetry: Any) -> MetricsStore:
    stores = getattr(telemetry, "stores", None)
    getter = getattr(stores, "get", None)
    if callable(getter):
        try:
            return getter()
        except Exception:
            pass
    return MetricsStore(default_db_path())


def _final_report(store: MetricsStore, run_id: str) -> dict[str, Any]:
    run = store.benchmark_run_record(run_id)
    if run is None:
        raise RuntimeError("benchmark run record missing")
    samples = store.benchmark_samples(run_id, include_warmups=True)
    return {
        "run": run,
        "comparison": calculate_comparison(samples),
        "samples": samples,
    }


def run_live_benchmark(
    ctx: Any,
    telemetry: Any,
    *,
    repeats: int = DEFAULT_REPEATS,
    warmups: int = DEFAULT_WARMUPS,
    include_network: bool = False,
    timeout_seconds: float = 180.0,
    fixture_path: Path | str = DEFAULT_FIXTURE_PATH,
    executable: str | None = None,
) -> dict[str, Any]:
    """Run explicit paid/local benchmark turns with process-scoped OFF/ON modes.

    The user's persistent Jev mode is never changed by the benchmark runner.
    """
    hermes_executable = executable or shutil.which("hermes")
    if not hermes_executable:
        raise RuntimeError("Hermes executable not found on PATH")

    fixtures = load_fixture_suite(
        fixture_path,
        include_network=include_network,
    )
    plan = build_plan(fixtures, repeats=repeats, warmups=warmups)
    run_id = plan[0].run_id
    config = read_config(ctx)
    store = _store_from_telemetry(telemetry)
    fixture_hash = fixture_set_hash(fixtures)

    environment = capture_environment(
        fixture_hash=fixture_hash,
        repeats=repeats,
        warmups=warmups,
        provider=config.provider,
        jev_model=config.model,
        hermes_version=detect_hermes_version(hermes_executable),
    )
    methodology = {
        "kind": "controlled_matched_benchmark",
        "modes": ["off", "on"],
        "warmups_excluded_from_deltas": True,
        "order_policy": "paired_alternating",
        "fixture_order": "stable",
        "read_only_default": True,
        "public_web_fixture_included": bool(include_network),
        "timeout_seconds": float(timeout_seconds),
        "sample_count": len(plan),
        "measured_sample_count": sum(1 for sample in plan if not sample.is_warmup),
    }

    store.start_benchmark_run(
        run_id=run_id,
        benchmark_version=BENCHMARK_VERSION,
        fixture_set_hash=fixture_hash,
        fixture_count=len(fixtures),
        repeats=repeats,
        warmups=warmups,
        environment=environment,
        methodology=methodology,
    )

    by_id = {fixture.fixture_id: fixture for fixture in fixtures}
    run_status = "complete"

    try:
        for sample in plan:
            fixture = by_id[sample.fixture_id]

            store.plan_benchmark_sample(
                sample_id=sample.sample_id,
                run_id=sample.run_id,
                fixture_id=sample.fixture_id,
                family=sample.family,
                mode=sample.mode,
                repeat_index=sample.repeat_index,
                order_index=sample.order_index,
                is_warmup=sample.is_warmup,
            )

            env = os.environ.copy()
            env.update(
                benchmark_env(
                    BenchmarkContext(
                        run_id=sample.run_id,
                        sample_id=sample.sample_id,
                        fixture_id=sample.fixture_id,
                        is_warmup=sample.is_warmup,
                    ),
                    mode=sample.mode,
                )
            )

            started = time.monotonic()
            exit_code: int | None = None
            validation_passed: bool | None = None
            error_category: str | None = None
            try:
                completed = subprocess.run(
                    [
                        hermes_executable,
                        "chat",
                        "--oneshot",
                        "-q",
                        fixture.prompt,
                    ],
                    cwd=str(PLUGIN_ROOT),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=max(10.0, float(timeout_seconds)),
                    check=False,
                )
                exit_code = int(completed.returncode)
                if fixture.validation_contains:
                    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
                    validation_passed = fixture.validation_contains in output
                else:
                    validation_passed = None
                if exit_code != 0:
                    error_category = "process_exit_nonzero"
            except Exception as exc:
                error_category = _safe_error_category(exc)

            elapsed_ms = max(0.0, (time.monotonic() - started) * 1000.0)
            row = store.finalize_benchmark_sample(
                sample.sample_id,
                runner_duration_ms=elapsed_ms,
                exit_code=exit_code,
                validation_passed=validation_passed,
                error_category=error_category,
            )
            if not sample.is_warmup and row.get("status") != "complete":
                run_status = "complete_with_failures"
    except Exception:
        run_status = "runner_error"
        raise
    finally:
        store.finish_benchmark_run(run_id, status=run_status)

    return _final_report(store, run_id)


def benchmark_plan_summary(
    *,
    repeats: int = DEFAULT_REPEATS,
    warmups: int = DEFAULT_WARMUPS,
    include_network: bool = False,
    fixture_path: Path | str = DEFAULT_FIXTURE_PATH,
) -> dict[str, Any]:
    fixtures = load_fixture_suite(fixture_path, include_network=include_network)
    plan = build_plan(fixtures, repeats=repeats, warmups=warmups, run_id="preview")
    return {
        "fixtures": [fixture.fixture_id for fixture in fixtures],
        "fixture_count": len(fixtures),
        "repeats": int(repeats),
        "warmups": int(warmups),
        "total_turns": len(plan),
        "measured_turns": sum(1 for sample in plan if not sample.is_warmup),
        "public_web_fixture_included": bool(include_network),
        "modes": ["off", "on"],
        "order_policy": "paired_alternating",
    }
