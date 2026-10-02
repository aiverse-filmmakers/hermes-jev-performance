"""Hermes Jev Performance plugin entry point.

Phase 1 intentionally performs no network I/O and registers no routing middleware.
"""

from .jevperf.plugin import register_plugin


def register(ctx) -> None:
    """Hermes plugin entry point."""
    register_plugin(ctx)
