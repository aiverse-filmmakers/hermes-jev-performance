"""Process-local benchmark correlation tags.

Only the explicit Phase 8 live benchmark runner sets these environment variables.
They contain random run/sample identifiers and public fixture identifiers, never prompts.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Mapping


RUN_ID_ENV = "HERMES_JEV_BENCHMARK_RUN_ID"
SAMPLE_ID_ENV = "HERMES_JEV_BENCHMARK_SAMPLE_ID"
FIXTURE_ID_ENV = "HERMES_JEV_BENCHMARK_FIXTURE_ID"
WARMUP_ENV = "HERMES_JEV_BENCHMARK_WARMUP"
MODE_ENV = "HERMES_JEV_BENCHMARK_MODE"

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


@dataclass(frozen=True)
class BenchmarkContext:
    run_id: str
    sample_id: str
    fixture_id: str
    is_warmup: bool


def _safe_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if _SAFE_ID.fullmatch(value) else None


def read_benchmark_context(
    environ: Mapping[str, str] | None = None,
) -> BenchmarkContext | None:
    env = os.environ if environ is None else environ
    run_id = _safe_id(env.get(RUN_ID_ENV))
    sample_id = _safe_id(env.get(SAMPLE_ID_ENV))
    fixture_id = _safe_id(env.get(FIXTURE_ID_ENV))
    if not all((run_id, sample_id, fixture_id)):
        return None
    return BenchmarkContext(
        run_id=run_id,
        sample_id=sample_id,
        fixture_id=fixture_id,
        is_warmup=str(env.get(WARMUP_ENV, "")).strip().lower() in {"1", "true", "yes"},
    )


def benchmark_env(context: BenchmarkContext, *, mode: str | None = None) -> dict[str, str]:
    result = {
        RUN_ID_ENV: context.run_id,
        SAMPLE_ID_ENV: context.sample_id,
        FIXTURE_ID_ENV: context.fixture_id,
        WARMUP_ENV: "1" if context.is_warmup else "0",
    }
    if mode in {"off", "on"}:
        result[MODE_ENV] = mode
    return result


def read_benchmark_mode(environ: Mapping[str, str] | None = None) -> str | None:
    env = os.environ if environ is None else environ
    if read_benchmark_context(env) is None:
        return None
    mode = str(env.get(MODE_ENV, "")).strip().lower()
    return mode if mode in {"off", "on"} else None
