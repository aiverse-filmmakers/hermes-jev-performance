"""Slash-command parsing, persistent controls, and concise stats."""

from __future__ import annotations

from typing import Any

from .compatibility import detect_compatibility
from .config import VALID_MODES, read_config


USAGE = (
    "Usage: /jev [status|on|off|shadow|stats|notice on|notice off|help]"
)


def _fmt_float(value: Any, suffix: str = "", digits: int = 1) -> str:
    if not isinstance(value, (int, float)):
        return "n/a"
    return f"{float(value):.{digits}f}{suffix}"


def render_status(ctx: Any, router_middleware: Any = None) -> str:
    config = read_config(ctx)
    compat = detect_compatibility(ctx)

    compatibility = "supported" if compat["phase1_supported"] else "degraded"
    routing_surface = "available" if compat["routing_surface_ready"] else "unavailable"
    persistent_settings = "available" if compat["persistent_settings_ready"] else "unavailable"
    warnings = ", ".join(config.warnings) if config.warnings else "none"

    last = getattr(router_middleware, "last_decision", None)
    if last is None:
        last_route = "none yet"
    else:
        confidence = (
            f"{last.confidence:.2f}"
            if isinstance(last.confidence, (int, float))
            else "n/a"
        )
        last_route = f"{last.family or 'fallback'} ({confidence}, {last.reason})"

    filter_reason = getattr(router_middleware, "last_filter_reason", None) or "none yet"

    return "\n".join(
        [
            "Hermes Jev Performance",
            f"Mode: {config.mode}",
            f"Provider: {config.provider}",
            f"Jev model: {config.model}",
            f"Minimum confidence: {config.min_confidence:.2f}",
            f"Timeout: {config.timeout_seconds:g}s",
            f"Notice: {'on' if config.notice else 'off'}",
            f"Telemetry: {'on' if config.telemetry_enabled else 'off'}",
            f"Retention: {config.retention_days} days",
            f"Hermes compatibility: {compatibility}",
            f"Routing middleware surface: {routing_surface}",
            f"Persistent settings surface: {persistent_settings}",
            f"Last route: {last_route}",
            f"Last filter state: {filter_reason}",
            f"Config warnings: {warnings}",
            "Phase: 6 (controls + telemetry)",
        ]
    )


def render_stats(telemetry: Any) -> str:
    if telemetry is None:
        return "Jev stats unavailable: telemetry observer is not active."
    try:
        stats = telemetry.summary(since_hours=24)
    except Exception:
        return "Jev stats unavailable: local metrics store could not be read."

    if stats.decisions == 0 and stats.turns == 0:
        return "Jev stats (last 24h)\nNo telemetry recorded yet."

    routes = ", ".join(f"{name}:{count}" for name, count in stats.routes) or "none"
    cost = (
        f"${stats.total_jev_cost_usd:.6f}"
        if isinstance(stats.total_jev_cost_usd, (int, float))
        else "n/a"
    )
    input_tokens = str(stats.input_tokens) if stats.input_tokens is not None else "n/a"
    output_tokens = str(stats.output_tokens) if stats.output_tokens is not None else "n/a"

    return "\n".join(
        [
            "Jev stats (last 24h)",
            f"Turns: {stats.turns}",
            f"Jev decisions: {stats.decisions}",
            f"Routes applied: {stats.applied}",
            f"Fallback/unrestricted: {stats.fallback}",
            f"Avg confidence: {_fmt_float(stats.avg_confidence, digits=2)}",
            f"Avg Jev latency: {_fmt_float(stats.avg_jev_latency_ms, 'ms', 0)}",
            f"Jev cost: {cost}",
            f"Avg Hermes turn: {_fmt_float(stats.avg_turn_duration_ms, 'ms', 0)}",
            f"Avg tool calls: {_fmt_float(stats.avg_tool_calls, digits=2)}",
            f"Avg LLM requests: {_fmt_float(stats.avg_llm_requests, digits=2)}",
            f"Input tokens: {input_tokens}",
            f"Output tokens: {output_tokens}",
            f"Routes: {routes}",
        ]
    )


def _set_setting(ctx: Any, key: str, value: Any) -> bool:
    setter = getattr(ctx, "set_config", None)
    if not callable(setter):
        return False
    try:
        setter(key, value)
        return True
    except Exception:
        return False


def set_mode(ctx: Any, mode: str, telemetry: Any = None, *, source: str = "command") -> str:
    normalized = str(mode or "").strip().lower()
    if normalized not in VALID_MODES:
        return USAGE

    before = read_config(ctx).mode
    if not _set_setting(ctx, "mode", normalized):
        return "Jev mode could not be changed: persistent plugin settings are unavailable."

    if telemetry is not None and before != normalized:
        try:
            telemetry.record_mode_change(before, normalized, source=source)
        except Exception:
            pass

    return f"Jev routing: {normalized.upper()}"


def set_notice(ctx: Any, enabled: bool) -> str:
    if not _set_setting(ctx, "notice", bool(enabled)):
        return "Jev notice could not be changed: persistent plugin settings are unavailable."
    return f"Jev reply notice: {'ON' if enabled else 'OFF'}"


def handle_jev_command(
    ctx: Any,
    raw: Any = "",
    router_middleware: Any = None,
    telemetry: Any = None,
) -> str:
    text = raw.strip().lower() if isinstance(raw, str) else ""

    if text in {"", "status"}:
        return render_status(ctx, router_middleware)
    if text in VALID_MODES:
        return set_mode(ctx, text, telemetry, source="slash")
    if text == "stats":
        return render_stats(telemetry)
    if text == "notice on":
        return set_notice(ctx, True)
    if text == "notice off":
        return set_notice(ctx, False)
    if text in {"help", "-h", "--help"}:
        return USAGE
    return USAGE


def build_command_handler(
    ctx: Any,
    router_middleware: Any = None,
    telemetry: Any = None,
):
    def _handler(raw: str = "") -> str:
        return handle_jev_command(ctx, raw, router_middleware, telemetry)

    return _handler
