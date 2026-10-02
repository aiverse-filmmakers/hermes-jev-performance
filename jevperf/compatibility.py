"""Feature-detect the Hermes plugin context without importing Hermes internals."""

from __future__ import annotations

from typing import Any


REQUIRED_PHASE1_METHODS = ("register_command", "get_config")
FUTURE_PUBLIC_METHODS = (
    "set_config",
    "register_middleware",
    "register_hook",
    "register_cli_command",
)


def detect_compatibility(ctx: Any) -> dict[str, object]:
    required = {name: callable(getattr(ctx, name, None)) for name in REQUIRED_PHASE1_METHODS}
    future = {name: callable(getattr(ctx, name, None)) for name in FUTURE_PUBLIC_METHODS}

    phase1_supported = all(required.values())
    routing_surface_ready = future["register_middleware"]
    persistent_settings_ready = future["set_config"]

    return {
        "phase1_supported": phase1_supported,
        "routing_surface_ready": routing_surface_ready,
        "persistent_settings_ready": persistent_settings_ready,
        "state_available": hasattr(ctx, "state"),
        "required": required,
        "future": future,
    }
