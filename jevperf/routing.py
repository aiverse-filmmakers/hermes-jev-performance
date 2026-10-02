"""Jev tool-family routing decision layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .client import JevError, choice_question, evaluate, safe_error_details
from .credentials import resolve_openrouter_credential
from .families import FAMILY_CRITERIA, ROUTING_FAMILIES


ROUTING_QUESTION = choice_question(
    (
        "Choose the single best tool-routing policy for the user's current request. "
        "Choose multi whenever completing the request genuinely requires more than "
        "one distinct tool family or restricting the turn to one family could block a "
        "necessary later step. Choose none only when no tool is needed."
    ),
    FAMILY_CRITERIA,
)


@dataclass(frozen=True)
class RoutingDecision:
    family: str | None
    confidence: float | None
    accepted: bool
    reason: str
    provider: str = "openrouter"
    requested_model: str | None = None
    actual_model: str | None = None
    latency_ms: float | None = None
    cost_usd: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    credential_source: str | None = None
    error_category: str | None = None
    error_status_code: int | None = None

    @property
    def can_filter(self) -> bool:
        return self.accepted and self.family not in {None, "none", "multi"}


class JevRouter:
    """Make one bounded routing decision from one fresh user-turn state."""

    def __init__(
        self,
        *,
        evaluator: Callable[..., dict[str, Any]] = evaluate,
        credential_resolver: Callable[[], Any] = resolve_openrouter_credential,
    ) -> None:
        self._evaluator = evaluator
        self._credential_resolver = credential_resolver

    def decide(
        self,
        state: str,
        *,
        provider: str,
        model: str,
        timeout_seconds: float,
        min_confidence: float,
    ) -> RoutingDecision:
        if provider != "openrouter":
            return RoutingDecision(
                family=None,
                confidence=None,
                accepted=False,
                reason="unsupported_provider",
                provider=provider,
                requested_model=model,
            )

        credential = self._credential_resolver()
        if credential is None:
            return RoutingDecision(
                family=None,
                confidence=None,
                accepted=False,
                reason="missing_credential",
                provider=provider,
                requested_model=model,
            )

        try:
            result = self._evaluator(
                token=credential.token,
                state=state,
                questions={"tool_family": ROUTING_QUESTION},
                model=model,
                timeout=timeout_seconds,
            )
        except JevError as exc:
            details = safe_error_details(exc)
            return RoutingDecision(
                family=None,
                confidence=None,
                accepted=False,
                reason="jev_error",
                provider=provider,
                requested_model=model,
                credential_source=credential.name,
                error_category=details.get("category"),
                error_status_code=details.get("status_code"),
            )
        except Exception:
            return RoutingDecision(
                family=None,
                confidence=None,
                accepted=False,
                reason="jev_error",
                provider=provider,
                requested_model=model,
                credential_source=credential.name,
                error_category="request",
            )

        answers = result.get("answers")
        answer = answers.get("tool_family", {}) if isinstance(answers, dict) else {}
        family = answer.get("choice")
        confidence = answer.get("confidence")

        if family not in ROUTING_FAMILIES:
            return RoutingDecision(
                family=None,
                confidence=None,
                accepted=False,
                reason="invalid_family",
                provider=provider,
                requested_model=model,
                actual_model=result.get("model"),
                latency_ms=result.get("latency_ms"),
                credential_source=credential.name,
            )

        confidence_value = (
            float(confidence)
            if type(confidence) in (int, float)
            else None
        )
        usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
        accepted = (
            confidence_value is not None
            and confidence_value >= min_confidence
        )

        return RoutingDecision(
            family=family,
            confidence=confidence_value,
            accepted=accepted,
            reason="accepted" if accepted else "low_or_missing_confidence",
            provider=provider,
            requested_model=result.get("requested_model", model),
            actual_model=result.get("model"),
            latency_ms=result.get("latency_ms"),
            cost_usd=usage.get("cost"),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            credential_source=credential.name,
        )
