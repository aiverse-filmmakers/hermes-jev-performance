"""Hermes compatibility feature detection and version metadata."""

from __future__ import annotations

import re
from typing import Any


MIN_HERMES_VERSION = "0.21.5"
SUPPORTED_PYTHON_MIN = (3, 11)
SUPPORTED_PYTHON_MAX = (3, 14)

REQUIRED_BASE_METHODS = ("register_command", "get_config")
ROUTING_METHODS = ("register_middleware",)
PERSISTENCE_METHODS = ("set_config",)
TELEMETRY_METHODS = ("register_hook",)
CLI_METHODS = ("register_cli_command",)

_SEMVER_RE = re.compile(r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)")


def parse_semver(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, str):
        return None
    match = _SEMVER_RE.search(value)
    if not match:
        return None
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
    )


def detect_hermes_version() -> str | None:
    """Read Hermes' public version identity when available, without invoking subprocesses."""
    try:
        from hermes_cli.version_info import get_version_info
    except Exception:
        try:
            import hermes_cli
            value = getattr(hermes_cli, "__version__", None)
            return str(value) if isinstance(value, str) and value.strip() else None
        except Exception:
            return None

    try:
        info = get_version_info()
    except Exception:
        return None

    for attr in ("base_version", "derived_version", "version"):
        value = getattr(info, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def version_meets_floor(
    version: object,
    *,
    minimum: str = MIN_HERMES_VERSION,
) -> bool | None:
    current = parse_semver(version)
    floor = parse_semver(minimum)
    if current is None or floor is None:
        return None
    return current >= floor


def _available(ctx: Any, names: tuple[str, ...]) -> dict[str, bool]:
    return {name: callable(getattr(ctx, name, None)) for name in names}


def detect_compatibility(ctx: Any) -> dict[str, object]:
    """Feature detection is authoritative; version is supporting metadata only."""
    required = _available(ctx, REQUIRED_BASE_METHODS)
    routing = _available(ctx, ROUTING_METHODS)
    persistence = _available(ctx, PERSISTENCE_METHODS)
    telemetry = _available(ctx, TELEMETRY_METHODS)
    cli = _available(ctx, CLI_METHODS)

    base_ready = all(required.values())
    routing_ready = all(routing.values())
    persistence_ready = all(persistence.values())
    telemetry_ready = all(telemetry.values())
    cli_ready = all(cli.values())

    version = detect_hermes_version()
    meets_floor = version_meets_floor(version)

    if not base_ready or meets_floor is False:
        level = "unsupported"
    elif routing_ready and persistence_ready and telemetry_ready:
        level = "supported"
    else:
        level = "degraded"

    return {
        "level": level,
        "phase1_supported": base_ready,
        "routing_surface_ready": routing_ready,
        "persistent_settings_ready": persistence_ready,
        "telemetry_hooks_ready": telemetry_ready,
        "cli_controls_ready": cli_ready,
        "state_available": hasattr(ctx, "state"),
        "hermes_version": version,
        "version_meets_floor": meets_floor,
        "minimum_hermes": MIN_HERMES_VERSION,
        "required": required,
        "future": {
            **routing,
            **persistence,
            **telemetry,
            **cli,
        },
    }
