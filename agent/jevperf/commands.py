"""Slash-command parsing, persistent controls, and concise stats."""

from __future__ import annotations

from typing import Any

from .compatibility import detect_compatibility
from .config import VALID_MODES, read_config
from .compaction_config import read_compaction_config
from .compaction_metrics import compaction_summary
from .doctor import render_doctor, run_doctor


USAGE = (
    "Usage: /jev [status|on|off|shadow|stats|doctor|compaction status|compaction off|compaction shadow|compaction on|compaction allow-external|compaction deny-external|notice on|notice off|help]"
)


def _fmt_float(value: Any, suffix: str = "", digits: int = 1) -> str:
    if not isinstance(value, (int, float)):
        return "n/a"
    return f"{float(value):.{digits}f}{suffix}"


def render_status(ctx: Any, router_middleware: Any = None) -> str:
    config = read_config(ctx)
    compat = detect_compatibility(ctx)

    compatibility = str(compat["level"])
    routing_surface = "available" if compat["routing_surface_ready"] else "unavailable"
    persistent_settings = "available" if compat["persistent_settings_ready"] else "unavailable"
    warnings = ", ".join(config.warnings) if config.warnings else "none"


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
            f"Config warnings: {warnings}",
            "Phase: 9 (hardening + packaging)",
            f"Compaction: {read_compaction_config(ctx).mode} (experimental; native context engine required)",
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
    total_cost = (
        f"${stats.total_jev_cost_usd:.6f}"
        if isinstance(stats.total_jev_cost_usd, (int, float))
        else "n/a"
    )
    avg_cost = (
        f"${stats.avg_jev_cost_usd:.8f}"
        if isinstance(stats.avg_jev_cost_usd, (int, float))
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
            f"Jev latency p50/p95: {_fmt_float(stats.p50_jev_latency_ms, 'ms', 0)} / {_fmt_float(stats.p95_jev_latency_ms, 'ms', 0)}",
            f"Avg Jev latency: {_fmt_float(stats.avg_jev_latency_ms, 'ms', 0)}",
            f"Jev cost avg/total: {avg_cost} / {total_cost}",
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


def compaction_control(ctx: Any, action: str = "status") -> str:
    if action in {"allow-external", "deny-external"}:
        enabled = action == "allow-external"
        if not _set_setting(ctx, "compaction_allow_external", enabled):
            return "Compaction external-data setting could not be changed: persistent settings are unavailable."
        return ("Compaction external transmission: " + ("ALLOWED" if enabled else "BLOCKED") +
                ". When allowed, compaction ON and SHADOW can send redacted textual constraints and conversation history, "
                "memory excerpts and complete redacted tool-output chunks to OpenRouter and incur charges. Routing has separate controls.")
    if action in VALID_MODES:
        if not _set_setting(ctx, "compaction_mode", action):
            return "Compaction mode could not be changed: persistent settings are unavailable."
        return (f"Jev compaction: {action.upper()}. Select context.engine: hermes-jev-performance "
                "in Hermes config and restart the agent/gateway to activate the native engine. "
                "External history/tool-output transmission requires the separate /jev compaction allow-external opt-in. "
                "Global /jev off suspends all Jev calls.")
    if action != "status":
        return USAGE
    config = read_compaction_config(ctx)
    try:
        metrics = compaction_summary()
    except Exception:
        metrics = {}
    return "\n".join([
        "Jev compaction (experimental)", f"Mode: {config.mode}",
        f"External history/memory/tool-output transmission: {'allowed' if config.allow_external else 'blocked'}",
        "Native engine selection: context.engine: hermes-jev-performance (restart required)",
        f"Global OFF suspension: {'yes' if read_config(ctx).mode == 'off' else 'no'}",
        f"Drop confidence: {config.drop_confidence:.2f}",
        f"Complete redacted assessment chunks: at most {config.chunk_chars} characters; every part must pass",
        f"Small outputs kept: below {config.min_drop_chars} characters",
        f"24h attempts/applied/fallback: {metrics.get('attempts', 'n/a')} / {metrics.get('applied', 'n/a')} / {metrics.get('fallback', 'n/a')}",
        f"Estimated context tokens saved: {metrics.get('estimated_tokens_saved', 'n/a')}",
        "Archives: private profile storage; recovery tool: jev_recover; 512 MiB capacity; no automatic deletion",
        f"Config warnings: {', '.join(config.warnings) or 'none'}",
    ])


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
    if text == "compaction" or text.startswith("compaction "):
        return compaction_control(ctx, text.partition(" ")[2] or "status")
    if text == "doctor":
        try:
            return render_doctor(run_doctor(ctx))
        except Exception:
            return "Jev doctor unavailable: local diagnostics could not complete."
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
