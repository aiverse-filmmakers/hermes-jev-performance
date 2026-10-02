"""Phase 1 plugin registration.

Registration is deliberately side-effect light:
- no network calls
- no provider/model changes
- no middleware yet
- one read-only /jev status command
"""

from __future__ import annotations

from typing import Any

from .commands import build_command_handler
from .compatibility import detect_compatibility


def register_plugin(ctx: Any) -> None:
    compat = detect_compatibility(ctx)
    if not compat["phase1_supported"]:
        # Raising during register makes Hermes disable only this plugin while
        # Hermes itself continues, which is safer than a partially wired plugin.
        raise RuntimeError(
            "Hermes Jev Performance requires public plugin context methods "
            "register_command and get_config."
        )

    ctx.register_command(
        "jev",
        build_command_handler(ctx),
        description="Jev routing/performance status and controls.",
        args_hint="[status|help]",
    )
