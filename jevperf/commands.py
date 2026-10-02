"""Slash-command parsing and Phase 1 status rendering."""

from __future__ import annotations

from typing import Any

from .compatibility import detect_compatibility
from .config import read_config


USAGE = "Usage: /jev [status|help]"


def render_status(ctx: Any) -> str:
    config = read_config(ctx)
    compat = detect_compatibility(ctx)

    compatibility = "supported" if compat["phase1_supported"] else "degraded"
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
            "Phase: 1 (skeleton only)",
            "Jev network calls: disabled",
            "Routing: not active yet",
        ]
    )


def handle_jev_command(ctx: Any, raw: Any = "") -> str:
    text = raw.strip().lower() if isinstance(raw, str) else ""

    if text in {"", "status"}:
        return render_status(ctx)
    if text in {"help", "-h", "--help"}:
        return USAGE
    return USAGE


def build_command_handler(ctx: Any):
    def _handler(raw: str = "") -> str:
        return handle_jev_command(ctx, raw)

    return _handler
