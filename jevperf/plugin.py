"""Hermes plugin registration."""

from __future__ import annotations

from typing import Any

from .commands import build_command_handler
from .compatibility import detect_compatibility
from .middleware import RoutingMiddleware


def register_plugin(ctx: Any) -> None:
    compat = detect_compatibility(ctx)
    if not compat["phase1_supported"]:
        raise RuntimeError(
            "Hermes Jev Performance requires public plugin context methods "
            "register_command and get_config."
        )

    router_middleware = RoutingMiddleware(ctx)

    ctx.register_command(
        "jev",
        build_command_handler(ctx, router_middleware),
        description="Jev routing/performance status and controls.",
        args_hint="[status|help]",
    )

    register_middleware = getattr(ctx, "register_middleware", None)
    if callable(register_middleware):
        register_middleware("llm_request", router_middleware)
