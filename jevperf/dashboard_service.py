"""Dashboard-facing service layer with no FastAPI dependency."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Mapping

from . import __version__
from .benchmark import calculate_comparison
from .benchmark_export import build_anonymized_export
from .config import VALID_MODES, ConfigSnapshot, read_config
from .store import MetricsStore, SCHEMA_VERSION, StatsSummary, default_db_path


PLUGIN_ID = "hermes-jev-performance"
PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class _MappingContext:
    def __init__(self, values: Mapping[str, Any]) -> None:
        self.values = dict(values)

    def get_config(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)


def _settings_values(field_loader: Callable[..., Any] | None = None) -> dict[str, Any]:
    if field_loader is None:
        from hermes_cli.plugins_settings import plugin_settings_fields
        field_loader = plugin_settings_fields

    fields = field_loader(PLUGIN_ID, PLUGIN_ROOT)
    values: dict[str, Any] = {}
    for field in fields or []:
        if not isinstance(field, Mapping):
            continue
        key = field.get("key")
        if not isinstance(key, str) or not key:
            continue
        if "value" in field:
            values[key] = field.get("value")
        elif "default" in field:
            values[key] = field.get("default")
    return values


def read_dashboard_config(
    field_loader: Callable[..., Any] | None = None,
) -> ConfigSnapshot:
    """Read current plugin settings through Hermes' canonical settings surface."""
    return read_config(_MappingContext(_settings_values(field_loader)))


def _empty_summary(hours: int) -> StatsSummary:
    return StatsSummary(
        since_hours=hours,
        decisions=0,
        turns=0,
        applied=0,
        fallback=0,
        avg_confidence=None,
        avg_jev_latency_ms=None,
        total_jev_cost_usd=None,
        avg_turn_duration_ms=None,
        avg_tool_calls=None,
        avg_llm_requests=None,
        input_tokens=None,
        output_tokens=None,
        routes=(),
    )


def summary_payload(
    *,
    hours: int = 24,
    store: MetricsStore | None = None,
) -> dict[str, Any]:
    """Return safe aggregate telemetry without exposing local paths or content."""
    bounded_hours = max(1, min(int(hours), 24 * 3650))
    db_path = default_db_path() if store is None else store.path
    if store is None and not db_path.exists():
        summary = _empty_summary(bounded_hours)
        database_state = "empty"
    else:
        active = store or MetricsStore(db_path)
        summary = active.summary(since_hours=bounded_hours)
        database_state = "ready"

    payload = asdict(summary)
    payload["routes"] = [
        {"family": family, "count": count}
        for family, count in summary.routes
    ]
    payload["database_state"] = database_state
    payload["schema_version"] = SCHEMA_VERSION
    return payload


def status_payload(
    *,
    field_loader: Callable[..., Any] | None = None,
    store: MetricsStore | None = None,
) -> dict[str, Any]:
    config = read_dashboard_config(field_loader)
    try:
        summary = summary_payload(hours=24, store=store)
        database_state = summary["database_state"]
        telemetry_error = None
    except Exception:
        summary = _empty_summary(24)
        summary = {
            **asdict(summary),
            "routes": [],
            "database_state": "error",
            "schema_version": SCHEMA_VERSION,
        }
        database_state = "error"
        telemetry_error = "metrics_unavailable"

    return {
        "plugin": {
            "id": PLUGIN_ID,
            "version": __version__,
        },
        "mode": config.mode,
        "provider": config.provider,
        "model": config.model,
        "min_confidence": config.min_confidence,
        "timeout_seconds": config.timeout_seconds,
        "notice": config.notice,
        "telemetry_enabled": config.telemetry_enabled,
        "retention_days": config.retention_days,
        "config_warnings": list(config.warnings),
        "telemetry": {
            "database_state": database_state,
            "schema_version": SCHEMA_VERSION,
            "error": telemetry_error,
        },
        "summary_24h": summary,
    }


def set_dashboard_mode(
    mode: str,
    *,
    settings_writer: Callable[..., Any] | None = None,
    field_loader: Callable[..., Any] | None = None,
    store: MetricsStore | None = None,
) -> dict[str, Any]:
    """Persist mode with Hermes' canonical plugin-settings writer and verify read-back."""
    normalized = str(mode or "").strip().lower()
    if normalized not in VALID_MODES:
        raise ValueError("mode must be one of: off, shadow, on")

    before = read_dashboard_config(field_loader).mode

    if settings_writer is None:
        from hermes_cli.plugins_settings import save_plugin_settings
        settings_writer = save_plugin_settings

    settings_writer(PLUGIN_ID, PLUGIN_ROOT, {"mode": normalized})
    after = read_dashboard_config(field_loader).mode

    if after != normalized:
        raise RuntimeError("mode write did not pass read-back verification")

    if before != after:
        try:
            active_store = store
            if active_store is None and default_db_path().exists():
                active_store = MetricsStore(default_db_path())
            if active_store is not None:
                active_store.record_mode_change(before, after, source="dashboard")
        except Exception:
            pass

    return {
        "ok": True,
        "previous_mode": before,
        "mode": after,
    }


def analytics_payload(
    *,
    hours: int = 24,
    limit: int = 30,
    store: MetricsStore | None = None,
) -> dict[str, Any]:
    """Dashboard analytics payload with aggregates only and no correlation keys."""
    bounded_hours = max(1, min(int(hours), 24 * 3650))
    bounded_limit = max(1, min(int(limit), 200))
    db_path = default_db_path() if store is None else store.path

    if store is None and not db_path.exists():
        return {
            "hours": bounded_hours,
            "database_state": "empty",
            "routes": [],
            "reasons": [],
            "comparison": [
                {"mode": mode, "turns": 0, "completed": 0, "errors": 0,
                 "avg_duration_ms": None, "avg_tool_calls": None,
                 "avg_llm_requests": None, "avg_input_tokens": None,
                 "avg_cached_input_tokens": None, "avg_output_tokens": None,
                 "avg_reasoning_tokens": None, "decisions": 0, "applied": 0,
                 "avg_jev_latency_ms": None, "avg_jev_confidence": None,
                 "total_jev_cost_usd": None}
                for mode in ("off", "shadow", "on")
            ],
            "series": [],
            "recent": [],
        }

    active = store or MetricsStore(db_path)
    summary = active.summary(since_hours=bounded_hours)
    return {
        "hours": bounded_hours,
        "database_state": "ready",
        "routes": [
            {"family": family, "count": count}
            for family, count in summary.routes
        ],
        "reasons": active.reason_breakdown(since_hours=bounded_hours),
        "comparison": active.mode_comparison(since_hours=bounded_hours),
        "series": active.time_series(since_hours=bounded_hours),
        "recent": active.recent_decisions(
            since_hours=bounded_hours,
            limit=bounded_limit,
        ),
    }


def benchmark_runs_payload(
    *,
    limit: int = 10,
    store: MetricsStore | None = None,
) -> dict[str, Any]:
    row_limit = max(1, min(int(limit), 50))
    db_path = default_db_path() if store is None else store.path
    if store is None and not db_path.exists():
        return {"database_state": "empty", "runs": []}

    active = store or MetricsStore(db_path)
    runs = []
    for run in active.list_benchmark_runs(limit=row_limit):
        samples = active.benchmark_samples(
            run["run_id"],
            include_warmups=True,
        )
        environment = run.get("environment")
        safe_environment = {
            key: environment.get(key)
            for key in (
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
            )
            if isinstance(environment, dict) and key in environment
        }
        measured = [sample for sample in samples if not sample.get("is_warmup")]
        failed = [sample for sample in measured if sample.get("status") != "complete"]
        runs.append(
            {
                "run_id": run["run_id"],
                "created_at": run["created_at"],
                "completed_at": run["completed_at"],
                "status": run["status"],
                "benchmark_version": run["benchmark_version"],
                "fixture_set_hash": run["fixture_set_hash"],
                "fixture_count": run["fixture_count"],
                "repeats": run["repeats"],
                "warmups": run["warmups"],
                "environment": safe_environment,
                "methodology": run.get("methodology", {}),
                "measured_samples": len(measured),
                "failed_samples": len(failed),
                "comparison": calculate_comparison(samples),
            }
        )
    return {"database_state": "ready", "runs": runs}


def benchmark_export_payload(
    run_id: str,
    *,
    store: MetricsStore | None = None,
) -> dict[str, Any]:
    db_path = default_db_path() if store is None else store.path
    if store is None and not db_path.exists():
        raise KeyError("benchmark run not found")
    active = store or MetricsStore(db_path)
    return build_anonymized_export(active, run_id)
