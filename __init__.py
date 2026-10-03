"""Hermes Jev Performance plugin entry point.

Also exposes the native ContextEngine through register_context_engine when supported.
Selecting it remains an explicit Hermes context.engine setting.
"""

from .jevperf.plugin import register_plugin


def register(ctx) -> None:
    """Hermes plugin entry point."""
    register_plugin(ctx)
