"""Hermes plugin registration."""

from __future__ import annotations

from typing import Any

from .cli import build_cli
from .commands import build_command_handler
from .compatibility import detect_compatibility
from .context_engine import register_compaction_engine
from .middleware import RoutingMiddleware
from .notice import build_notice_hook
from .telemetry import TelemetryObserver


def register_plugin(ctx: Any) -> None:
    # Hermes' dedicated engine loader supplies an engine-only collector, not PluginContext.
    if not callable(getattr(ctx, "get_config", None)) and callable(getattr(ctx, "register_context_engine", None)):
        register_compaction_engine(ctx)
        return
    compat = detect_compatibility(ctx)
    if not compat["phase1_supported"]:
        raise RuntimeError(
            "Hermes Jev Performance requires public plugin context methods "
            "register_command and get_config."
        )

    telemetry = TelemetryObserver(ctx)
    router_middleware = RoutingMiddleware(ctx, telemetry=telemetry)
    register_compaction_engine(ctx)

    ctx.register_command(
        "jev",
        build_command_handler(ctx, router_middleware, telemetry),
        description="Jev routing/performance status and controls.",
        args_hint="[status|on|off|shadow|stats|doctor|compaction status|compaction off|compaction shadow|compaction on|compaction allow-external|compaction deny-external|notice on|notice off|help]",
    )

    register_middleware = getattr(ctx, "register_middleware", None)
    if callable(register_middleware):
        register_middleware("llm_request", router_middleware)

    register_hook = getattr(ctx, "register_hook", None)
    if callable(register_hook):
        register_hook("pre_api_request", telemetry.on_pre_api_request)
        register_hook("post_api_request", telemetry.on_post_api_request)
        register_hook("post_tool_call", telemetry.on_post_tool_call)
        register_hook("on_session_end", telemetry.on_session_end)
        register_hook("transform_llm_output", build_notice_hook(ctx, router_middleware))

    register_cli = getattr(ctx, "register_cli_command", None)
    if callable(register_cli):
        setup, handler = build_cli(ctx, router_middleware, telemetry)
        register_cli(
            name="jev",
            help="Control Jev routing and inspect local performance stats",
            setup_fn=setup,
            handler_fn=handler,
            description="Jev routing, shadow mode, notices, and local performance telemetry.",
        )
