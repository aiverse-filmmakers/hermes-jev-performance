"""Server-only and combined Hermes package entry point."""

from .jevperf.plugin import register_plugin


def register(ctx) -> None:
    """Register Jev routing, telemetry, commands, and the optional context engine."""
    register_plugin(ctx)
