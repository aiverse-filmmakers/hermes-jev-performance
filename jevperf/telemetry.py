"""Content-free Hermes observer hooks for local performance telemetry."""

from __future__ import annotations

from collections import OrderedDict
import threading
import time
from typing import Any

from .benchmark_context import read_benchmark_context
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
        self._seen_turns: OrderedDict[tuple[str, str], None] = OrderedDict()
        self._seen_lock = threading.Lock()
        self._last_cleanup: dict[str, float] = {}
        self._cleanup_lock = threading.Lock()

    def _touch_once(self, store: Any, key: str, mode: str, benchmark: Any = None) -> None:
        identity = (str(getattr(store, "path", "")), key)
        with self._seen_lock:
            if identity in self._seen_turns:
                self._seen_turns.move_to_end(identity)
                return
            self._seen_turns[identity] = None
            self._seen_turns.move_to_end(identity)
            while len(self._seen_turns) > 2048:
                self._seen_turns.popitem(last=False)
        _safe_call(store.touch_turn, key, mode, benchmark=benchmark)

    def _cleanup_if_due(self, store: Any, retention_days: int) -> None:
        identity = str(getattr(store, "path", ""))
        now = time.monotonic()
        with self._cleanup_lock:
            previous = self._last_cleanup.get(identity)
            if previous is not None and now - previous < 3600:
                return
            self._last_cleanup[identity] = now
        _safe_call(store.cleanup, retention_days)

    def start_turn(self, session_id: Any, turn_id: Any, *, mode: str | None = None) -> str | None:
        key = turn_key(session_id, turn_id)
        if key is None:
            return None
        config = read_config(self.ctx)
        if not config.telemetry_enabled:
            return key
        store = self.stores.get()
        benchmark = read_benchmark_context()
        self._touch_once(store, key, mode or config.mode, benchmark)
        self._cleanup_if_due(store, config.retention_days)
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

    def record_turn_reason(
        self,
        *,
        session_id: Any,
        turn_id: Any,
        mode: str,
        reason: str,
    ) -> None:
        key = self.start_turn(session_id, turn_id, mode=mode)
        if key is None or not read_config(self.ctx).telemetry_enabled:
            return
        _safe_call(self.stores.get().record_turn_reason, key, reason)

    def on_pre_api_request(self, **kwargs: Any) -> None:
        key = self.start_turn(kwargs.get("session_id"), kwargs.get("turn_id"))
        if key is None or not read_config(self.ctx).telemetry_enabled:
            return
        _safe_call(self.stores.get().increment_llm_request, key)

    def on_post_api_request(self, **kwargs: Any) -> None:
        key = turn_key(kwargs.get("session_id"), kwargs.get("turn_id"))
        if key is None or not read_config(self.ctx).telemetry_enabled:
            return
        usage = kwargs.get("usage")
        _safe_call(
            self.stores.get().add_usage,
            key,
            usage if isinstance(usage, dict) else None,
        )

    def on_post_tool_call(self, **kwargs: Any) -> None:
        key = turn_key(kwargs.get("session_id"), kwargs.get("turn_id"))
        if key is None or not read_config(self.ctx).telemetry_enabled:
            return
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
