"""Content-free Hermes observer hooks for local performance telemetry."""

from __future__ import annotations

from typing import Any

from .config import read_config
from .store import StoreProvider
from .turns import turn_key


def _safe_call(callback, *args, **kwargs):
    try:
        return callback(*args, **kwargs)
    except Exception:
        return None


class TelemetryObserver:
    """Collect metadata only. Hook payload content fields are intentionally ignored."""

    def __init__(self, ctx: Any, stores: StoreProvider | None = None) -> None:
        self.ctx = ctx
        self.stores = stores or StoreProvider()

    def start_turn(self, session_id: Any, turn_id: Any, *, mode: str | None = None) -> str | None:
        key = turn_key(session_id, turn_id)
        if key is None:
            return None
        config = read_config(self.ctx)
        if not config.telemetry_enabled:
            return key
        store = self.stores.get()
        _safe_call(store.touch_turn, key, mode or config.mode)
        _safe_call(store.cleanup, config.retention_days)
        return key

    def record_decision(
        self,
        *,
        session_id: Any,
        turn_id: Any,
        mode: str,
        decision: Any,
        applied: bool,
        reason: str,
    ) -> None:
        key = self.start_turn(session_id, turn_id, mode=mode)
        if key is None or decision is None:
            return
        if not read_config(self.ctx).telemetry_enabled:
            return
        _safe_call(
            self.stores.get().record_decision,
            turn_key=key,
            mode=mode,
            decision=decision,
            applied=applied,
            reason=reason,
        )

    def on_pre_api_request(self, **kwargs: Any) -> None:
        key = self.start_turn(kwargs.get("session_id"), kwargs.get("turn_id"))
        if key is None or not read_config(self.ctx).telemetry_enabled:
            return
        _safe_call(self.stores.get().increment_llm_request, key)

    def on_post_api_request(self, **kwargs: Any) -> None:
        key = turn_key(kwargs.get("session_id"), kwargs.get("turn_id"))
        if key is None or not read_config(self.ctx).telemetry_enabled:
            return
        # Deliberately read only accounting metadata. Ignore response,
        # assistant_message, request_messages and all other content-bearing fields.
        usage = kwargs.get("usage")
        _safe_call(self.stores.get().add_usage, key, usage if isinstance(usage, dict) else None)

    def on_post_tool_call(self, **kwargs: Any) -> None:
        key = turn_key(kwargs.get("session_id"), kwargs.get("turn_id"))
        if key is None or not read_config(self.ctx).telemetry_enabled:
            return
        # Deliberately ignore tool_name, args, result, error_message and paths.
        _safe_call(self.stores.get().increment_tool_call, key)

    def on_session_end(self, **kwargs: Any) -> None:
        key = turn_key(kwargs.get("session_id"), kwargs.get("turn_id"))
        if key is None or not read_config(self.ctx).telemetry_enabled:
            return

        if bool(kwargs.get("interrupted")):
            status = "interrupted"
        elif bool(kwargs.get("failed")):
            status = "error"
        elif bool(kwargs.get("completed")):
            status = "complete"
        else:
            status = "unknown"
        _safe_call(self.stores.get().finish_turn, key, status=status)

    def summary(self, *, since_hours: int = 24):
        return self.stores.get().summary(since_hours=since_hours)

    def record_mode_change(self, old_mode: str, new_mode: str, *, source: str) -> None:
        if not read_config(self.ctx).telemetry_enabled:
            return
        _safe_call(
            self.stores.get().record_mode_change,
            old_mode,
            new_mode,
            source=source,
        )
