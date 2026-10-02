"""Hermes llm_request middleware for conservative Jev tool routing."""

from __future__ import annotations

from typing import Any

from .config import read_config
from .families import filter_tools
from .routing import JevRouter, RoutingDecision
from .turns import TurnDecisionCache, extract_routing_state, turn_key


class RoutingMiddleware:
    """One Jev decision per fresh turn, reused through the tool loop."""

    def __init__(
        self,
        ctx: Any,
        *,
        router: JevRouter | None = None,
        cache: TurnDecisionCache | None = None,
    ) -> None:
        self.ctx = ctx
        self.router = router or JevRouter()
        self.cache = cache or TurnDecisionCache()
        self.last_decision: RoutingDecision | None = None
        self.last_filter_reason: str | None = None

    def _decision_for_turn(
        self,
        request: dict[str, Any],
        *,
        key: str,
        config: Any,
    ) -> RoutingDecision | None:
        cached = self.cache.get(key)
        if isinstance(cached, RoutingDecision):
            return cached

        state = extract_routing_state(request)
        if not state:
            return None

        decision = self.router.decide(
            state,
            provider=config.provider,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            min_confidence=config.min_confidence,
        )
        self.cache.put(key, decision)
        return decision

    def __call__(self, **kwargs: Any) -> dict[str, Any] | None:
        """Return a complete replacement request only when ON mode safely filters."""
        try:
            request = kwargs.get("request")
            if not isinstance(request, dict):
                return None

            config = read_config(self.ctx)
            if config.mode == "off":
                self.last_filter_reason = "mode_off"
                return None

            key = turn_key(kwargs.get("session_id"), kwargs.get("turn_id"))
            if key is None:
                self.last_filter_reason = "missing_turn_id"
                return None

            decision = self._decision_for_turn(
                request,
                key=key,
                config=config,
            )
            self.last_decision = decision
            if decision is None:
                self.last_filter_reason = "missing_user_state"
                return None

            if config.mode == "shadow":
                self.last_filter_reason = "shadow"
                return None

            if not decision.can_filter:
                self.last_filter_reason = decision.reason
                return None

            tools = request.get("tools")
            filtered, applied, reason = filter_tools(tools, decision.family or "")
            self.last_filter_reason = reason
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
