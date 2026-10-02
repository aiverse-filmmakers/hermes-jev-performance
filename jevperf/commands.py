"""Slash-command parsing and routing status rendering."""

from __future__ import annotations

from typing import Any

from .compatibility import detect_compatibility
from .config import read_config


USAGE = "Usage: /jev [status|help]"


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
            "Phase: 4 (routing middleware)",
        ]
    )


def handle_jev_command(
    ctx: Any,
    raw: Any = "",
    router_middleware: Any = None,
) -> str:
    text = raw.strip().lower() if isinstance(raw, str) else ""

    if text in {"", "status"}:
        return render_status(ctx, router_middleware)
    if text in {"help", "-h", "--help"}:
        return USAGE
    return USAGE


def build_command_handler(ctx: Any, router_middleware: Any = None):
    def _handler(raw: str = "") -> str:
        return handle_jev_command(ctx, raw, router_middleware)

    return _handler
