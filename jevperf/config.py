"""Validated plugin configuration.

No secrets are read in Phase 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


VALID_MODES = frozenset({"off", "shadow", "on"})

DEFAULT_MODE = "shadow"
DEFAULT_PROVIDER = "openrouter"
DEFAULT_MODEL = "typesafe/jev-1.13"
DEFAULT_MIN_CONFIDENCE = 0.70
DEFAULT_TIMEOUT_SECONDS = 2.5
DEFAULT_NOTICE = False
DEFAULT_RETENTION_DAYS = 30
DEFAULT_TELEMETRY_ENABLED = True


@dataclass(frozen=True)
class ConfigSnapshot:
    mode: str
    provider: str
    model: str
    min_confidence: float
    timeout_seconds: float
    notice: bool
    retention_days: int
    telemetry_enabled: bool
    warnings: tuple[str, ...] = ()


def _get(ctx: Any, key: str, default: Any) -> Any:
    getter = getattr(ctx, "get_config", None)
    if not callable(getter):
        return default
    try:
        return getter(key, default)
    except Exception:
        return default


def _clean_string(value: Any, default: str) -> str:
    if not isinstance(value, str):
        return default
    value = value.strip()
    return value or default


def _clean_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _clean_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if minimum <= number <= maximum:
        return number
    return default


def _clean_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if minimum <= number <= maximum:
        return number
    return default


def read_config(ctx: Any) -> ConfigSnapshot:
    """Read and normalize non-secret settings without mutating disk."""
    warnings: list[str] = []

    raw_mode = _get(ctx, "mode", DEFAULT_MODE)
    mode = raw_mode.strip().lower() if isinstance(raw_mode, str) else DEFAULT_MODE
    if mode not in VALID_MODES:
        warnings.append("invalid_mode_fallback")
        mode = DEFAULT_MODE

    provider = _clean_string(_get(ctx, "provider", DEFAULT_PROVIDER), DEFAULT_PROVIDER).lower()
    model = _clean_string(_get(ctx, "model", DEFAULT_MODEL), DEFAULT_MODEL)

    raw_confidence = _get(ctx, "min_confidence", DEFAULT_MIN_CONFIDENCE)
    min_confidence = _clean_float(raw_confidence, DEFAULT_MIN_CONFIDENCE, 0.0, 1.0)
    if min_confidence != raw_confidence and not (
        isinstance(raw_confidence, (int, float)) and not isinstance(raw_confidence, bool)
        and float(raw_confidence) == min_confidence
    ):
        warnings.append("invalid_min_confidence_fallback")

    raw_timeout = _get(ctx, "timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    timeout_seconds = _clean_float(raw_timeout, DEFAULT_TIMEOUT_SECONDS, 0.1, 30.0)
    if timeout_seconds != raw_timeout and not (
        isinstance(raw_timeout, (int, float)) and not isinstance(raw_timeout, bool)
        and float(raw_timeout) == timeout_seconds
    ):
        warnings.append("invalid_timeout_fallback")

    raw_notice = _get(ctx, "notice", DEFAULT_NOTICE)
    notice = _clean_bool(raw_notice, DEFAULT_NOTICE)
    if not isinstance(raw_notice, bool):
        warnings.append("invalid_notice_fallback")

    raw_retention = _get(ctx, "retention_days", DEFAULT_RETENTION_DAYS)
    retention_days = _clean_int(raw_retention, DEFAULT_RETENTION_DAYS, 1, 3650)
    if retention_days != raw_retention and not (
        isinstance(raw_retention, int) and not isinstance(raw_retention, bool)
        and raw_retention == retention_days
    ):
        warnings.append("invalid_retention_fallback")

    raw_telemetry = _get(ctx, "telemetry_enabled", DEFAULT_TELEMETRY_ENABLED)
    telemetry_enabled = _clean_bool(raw_telemetry, DEFAULT_TELEMETRY_ENABLED)
    if not isinstance(raw_telemetry, bool):
        warnings.append("invalid_telemetry_fallback")

    return ConfigSnapshot(
        mode=mode,
        provider=provider,
        model=model,
        min_confidence=min_confidence,
        timeout_seconds=timeout_seconds,
        notice=notice,
        retention_days=retention_days,
        telemetry_enabled=telemetry_enabled,
        warnings=tuple(warnings),
    )
