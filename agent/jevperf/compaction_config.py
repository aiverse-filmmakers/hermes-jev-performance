"""Independent, conservative compaction settings. Invalid settings disable it."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .config import _get


@dataclass(frozen=True)
class CompactionConfig:
    mode: str = "off"
    drop_confidence: float = 0.90
    min_drop_chars: int = 1500
    preview_chars: int = 600
    preserve_recent_messages: int = 6
    max_state_tokens: int = 14000
    max_request_tokens: int = 30000
    min_reduction_ratio: float = 0.25
    max_batches: int = 8
    deadline_seconds: float = 10.0
    warnings: tuple[str, ...] = ()


def read_compaction_config(ctx: Any) -> CompactionConfig:
    defaults = CompactionConfig()
    values: dict[str, Any] = {}
    warnings = []
    bounds = {
        "drop_confidence": (0.5, 1.0), "min_drop_chars": (200, 1000000),
        "preview_chars": (100, 4000), "preserve_recent_messages": (2, 1000),
        "max_state_tokens": (500, 26000), "max_request_tokens": (1000, 30000),
        "min_reduction_ratio": (0.05, 0.95), "max_batches": (1, 32),
        "deadline_seconds": (0.1, 30.0),
    }
    mode = _get(ctx, "compaction_mode", defaults.mode)
    if mode not in {"off", "shadow", "on"}:
        warnings.append("invalid_compaction_mode")
        mode = "off"
    for name, (lower, upper) in bounds.items():
        default = getattr(defaults, name)
        value = _get(ctx, "compaction_" + name, default)
        valid = type(value) in (int, float) and math.isfinite(value) and lower <= value <= upper
        if type(default) is int:
            valid = valid and type(value) is int
        if not valid:
            warnings.append("invalid_compaction_" + name)
            value = default
        values[name] = value
    if values["max_state_tokens"] + 500 >= values["max_request_tokens"]:
        warnings.append("invalid_compaction_token_budgets")
    return CompactionConfig(mode="off" if warnings else mode, warnings=tuple(warnings), **values)
