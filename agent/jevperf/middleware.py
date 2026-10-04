"""Hermes llm_request middleware for conservative Jev tool routing."""

from __future__ import annotations

from collections import OrderedDict
import threading
from typing import Any

from .config import read_config
from .families import filter_tools
from .routing import JevRouter, RoutingDecision
from .turns import TurnDecisionCache, decision_key, extract_routing_state, turn_key


class RoutingMiddleware:
    """One Jev decision per fresh turn; changed inputs restore all tools."""

    def __init__(
        self,
        ctx: Any,
        *,
        router: JevRouter | None = None,
        cache: TurnDecisionCache | None = None,
        telemetry: Any = None,
    ) -> None:
        self.ctx = ctx
        self.router = router or JevRouter()
        self.cache = cache if cache is not None else TurnDecisionCache()
        self.telemetry = telemetry
        self.last_decision: RoutingDecision | None = None
        self.last_filter_reason: str | None = None
        self._latest_by_session: OrderedDict[str, tuple[RoutingDecision, str, str]] = OrderedDict()
        self._latest_lock = threading.Lock()

    def _telemetry_call(self, name: str, *args: Any, **kwargs: Any) -> None:
        target = getattr(self.telemetry, name, None)
        if not callable(target):
            return
        try:
            target(*args, **kwargs)
        except Exception:
            # Telemetry is never allowed to affect routing.
            return

    def _remember_session(
        self,
        session_id: Any,
        decision: RoutingDecision | None,
        *,
        mode: str,
        reason: str,
    ) -> None:
        session = str(session_id or "").strip()
        if not session:
            return
        with self._latest_lock:
            if decision is None:
                self._latest_by_session.pop(session, None)
                return
            self._latest_by_session[session] = (decision, mode, reason)
            self._latest_by_session.move_to_end(session)
            while len(self._latest_by_session) > 256:
                self._latest_by_session.popitem(last=False)

    def latest_for_session(
        self,
        session_id: Any,
    ) -> tuple[RoutingDecision, str, str] | None:
        session = str(session_id or "").strip()
        if not session:
            return None
        with self._latest_lock:
            value = self._latest_by_session.get(session)
            if value is not None:
                self._latest_by_session.move_to_end(session)
            return value

    def _decision_for_turn(
        self,
        request: dict[str, Any],
        *,
        key: str,
        config: Any,
    ) -> RoutingDecision | None:
        state = extract_routing_state(request)
        if not state:
            # Once this turn becomes unusable, an older request must not revive
            # its restriction if the host later presents a truncated transcript.
            self.cache.put(key, (None, None))
            return None
        fingerprint = decision_key(key, state, config)

        def compute():
            try:
                decision = self.router.decide(
                    state,
                    provider=config.provider,
                    model=config.model,
                    timeout_seconds=config.timeout_seconds,
                    min_confidence=config.min_confidence,
                )
            except Exception:
                self.cache.put(key, (None, None))
                raise
            return fingerprint, decision

        cached_fingerprint, decision = self.cache.get_or_compute(key, compute)
        if cached_fingerprint != fingerprint:
            # Changed state/config fails open for the rest of this turn. No
            # extra paid decisions (or untracked same-turn provider charges).
            self.cache.put(key, (None, None))
            return None
        return decision if isinstance(decision, RoutingDecision) else None

    def _record(
        self,
        *,
        session_id: Any,
        turn_id: Any,
        config: Any,
        decision: RoutingDecision | None,
        applied: bool,
        reason: str,
    ) -> None:
        self._remember_session(
            session_id,
            decision,
            mode=config.mode,
            reason=reason,
        )
        if decision is None:
            return
        self._telemetry_call(
            "record_decision",
            session_id=session_id,
            turn_id=turn_id,
            mode=config.mode,
            decision=decision,
            applied=applied,
            reason=reason,
        )

    def __call__(self, **kwargs: Any) -> dict[str, Any] | None:
        """Return a complete replacement request only when ON mode safely filters."""
        session_id = kwargs.get("session_id")
        turn_id = kwargs.get("turn_id")
        try:
            request = kwargs.get("request")
            if not isinstance(request, dict):
                return None

            config = read_config(self.ctx)
            key = turn_key(session_id, turn_id)
            if key is not None:
                self._telemetry_call(
                    "start_turn",
                    session_id,
                    turn_id,
                    mode=config.mode,
                )

            if config.mode == "off":
                if key is not None and self.cache.get(key) is not None:
                    self.cache.put(key, (None, None))
                self.last_decision = None
                self.last_filter_reason = "mode_off"
                self._remember_session(session_id, None, mode=config.mode, reason="mode_off")
                self._telemetry_call(
                    "record_turn_reason",
                    session_id=session_id,
                    turn_id=turn_id,
                    mode=config.mode,
                    reason="mode_off",
                )
                return None

            if key is None:
                self.last_filter_reason = "missing_turn_id"
                return None

            # Named/required/unknown provider choices are authoritative. Bypass
            # routing entirely so filtering cannot invalidate a forced request.
            if request.get("tool_choice") not in (None, "auto"):
                self.cache.put(key, (None, None))
                self.last_decision = None
                self.last_filter_reason = "explicit_tool_choice"
                self._remember_session(session_id, None, mode=config.mode, reason=self.last_filter_reason)
                return None

            decision = self._decision_for_turn(
                request,
                key=key,
                config=config,
            )
            self.last_decision = decision
            if decision is None:
                self.last_filter_reason = "missing_user_state"
                self._remember_session(
                    session_id,
                    None,
                    mode=config.mode,
                    reason="missing_user_state",
                )
                self._telemetry_call(
                    "record_turn_reason",
                    session_id=session_id,
                    turn_id=turn_id,
                    mode=config.mode,
                    reason="missing_user_state",
                )
                return None

            if config.mode == "shadow":
                self.last_filter_reason = "shadow"
                self._record(
                    session_id=session_id,
                    turn_id=turn_id,
                    config=config,
                    decision=decision,
                    applied=False,
                    reason="shadow",
                )
                return None

            if not decision.can_filter:
                if decision.accepted and decision.family in {"none", "multi", "none_of_these"}:
                    reason = f"unrestricted_{decision.family}"
                else:
                    reason = decision.reason
                self.last_filter_reason = reason
                self._record(
                    session_id=session_id,
                    turn_id=turn_id,
                    config=config,
                    decision=decision,
                    applied=False,
                    reason=reason,
                )
                return None

            tools = request.get("tools")
            filtered, applied, reason = filter_tools(tools, decision.family or "")
            self.last_filter_reason = reason
            self._record(
                session_id=session_id,
                turn_id=turn_id,
                config=config,
                decision=decision,
                applied=applied,
                reason=reason,
            )
            if not applied:
                return None

            updated = dict(request)
            updated["tools"] = filtered
            return {
                "request": updated,
                "source": "hermes-jev-performance",
                "reason": f"jev:{decision.family}",
            }
        except Exception:
            self.last_filter_reason = "middleware_error"
            return None
