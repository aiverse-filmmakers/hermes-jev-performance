"""Optional concise Jev routing footer for final Hermes replies."""

from __future__ import annotations

from typing import Any

from .config import read_config


NOTICE_PREFIX = "[Jev"


def build_notice_hook(ctx: Any, router_middleware: Any):
    def _transform(
        response_text: str = "",
        session_id: str = "",
        **_: Any,
    ) -> str | None:
        try:
            config = read_config(ctx)
            if not config.notice or config.mode == "off":
                return None
            if not isinstance(response_text, str) or not response_text:
                return None
            if NOTICE_PREFIX in response_text:
                return None

            latest = router_middleware.latest_for_session(session_id)
            if latest is None:
                return None
            decision, mode, _reason = latest
            family = decision.family or "fallback"
            confidence = (
                f"{decision.confidence * 100:.0f}%"
                if isinstance(decision.confidence, (int, float))
                else "n/a"
            )
            latency = (
                f"{decision.latency_ms:.0f}ms"
                if isinstance(decision.latency_ms, (int, float))
                else "n/a"
            )
            label = "Jev shadow" if mode == "shadow" else "Jev"
            return f"{response_text}\n\n[{label}] {family} · {confidence} · {latency}"
        except Exception:
            return None

    return _transform
