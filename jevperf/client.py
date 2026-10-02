"""Bounded OpenRouter Jev Decisions API client.

Adapted in part from:
- ourines/hermes-jev client.py, MIT, reference commit
  cdf59e46270d3b33618d3b275c5c2fb76f594a19
- kerpopule/hermes-jev-skills jevkit/client.py, MIT, reference commit
  4e9b3677a9d482d661419441782589883634cfe3

This project intentionally keeps only the OpenRouter Decisions path needed by
Hermes Jev Performance. It is not a generic OpenRouter proxy.
"""

from __future__ import annotations

import json
import math
import re
import socket
import time
from typing import Any
import urllib.error
import urllib.request


OPENROUTER_DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_JEV_MODEL = "typesafe/jev-1.13"

MAX_QUESTIONS = 128
MAX_CHOICE_OPTIONS = 255
MAX_SCORE_LEVELS = 10
MAX_PAYLOAD_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_STATE_DEPTH = 64


class JevError(Exception):
    """Display-safe Jev client error with no raw provider/user content."""

    _CATEGORIES = frozenset({
        "request",
        "http",
        "timeout",
        "network",
        "invalid_token",
        "invalid_model",
        "invalid_timeout",
        "invalid_state",
        "invalid_questions",
        "invalid_payload",
        "invalid_json",
        "invalid_response",
        "payload_too_large",
        "response_too_large",
    })

    def __init__(
        self,
        category: str = "request",
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        self.category = category if category in self._CATEGORIES else "request"
        self.status_code = (
            status_code
            if isinstance(status_code, int) and 100 <= status_code <= 599
            else None
        )
        self.retryable = retryable is True
        message = f"Jev {self.category} error"
        if self.status_code is not None:
            message += f" ({self.status_code})"
        super().__init__(message)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def safe_error_details(error: Exception) -> dict[str, Any]:
    """Return allowlisted diagnostics only."""
    if not isinstance(error, JevError):
        return {}
    return {
        "category": error.category,
        "status_code": error.status_code,
        "retryable": error.retryable,
        "message": str(error),
    }


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _json_value(value: Any, depth: int = 0) -> bool:
    if depth > MAX_STATE_DEPTH:
        return False
    if value is None or type(value) in (bool, int):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is str:
        return not any(0xD800 <= ord(char) <= 0xDFFF for char in value)
    if type(value) is list:
        return all(_json_value(item, depth + 1) for item in value)
    if type(value) is dict:
        return all(
            type(key) is str
            and _json_value(key, depth + 1)
            and _json_value(item, depth + 1)
            for key, item in value.items()
        )
    return False


def _encode_payload(payload: dict[str, Any]) -> bytes:
    try:
        raw = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise JevError("invalid_payload") from None
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise JevError("payload_too_large")
    return raw


def _validate_state(state: Any) -> None:
    if type(state) not in (str, dict, list):
        raise JevError("invalid_state")
    if isinstance(state, str) and not state.strip():
        raise JevError("invalid_state")
    if not _json_value(state):
        raise JevError("invalid_state")


def _validate_questions(questions: Any) -> None:
    if (
        type(questions) is not dict
        or not 1 <= len(questions) <= MAX_QUESTIONS
        or not _json_value(questions)
    ):
        raise JevError("invalid_questions")

    for name, question in questions.items():
        if not _text(name) or type(question) is not dict:
            raise JevError("invalid_questions")

        kind = question.get("type")
        instructions = question.get("instructions")
        if kind not in {"noul", "choice", "score"} or not _text(instructions):
            raise JevError("invalid_questions")

        criteria = question.get("criteria")
        if kind == "noul":
            if "criteria" not in question:
                continue
            if (
                type(criteria) is not dict
                or not criteria
                or not set(criteria).issubset({"true", "false"})
                or not all(_text(value) for value in criteria.values())
            ):
                raise JevError("invalid_questions")
        elif kind == "choice":
            if (
                type(criteria) is not dict
                or not 2 <= len(criteria) <= MAX_CHOICE_OPTIONS
                or not all(
                    _text(key) and (value is None or isinstance(value, str))
                    for key, value in criteria.items()
                )
            ):
                raise JevError("invalid_questions")
        else:
            if (
                type(criteria) is not list
                or not 2 <= len(criteria) <= MAX_SCORE_LEVELS
                or not all(_text(value) for value in criteria)
            ):
                raise JevError("invalid_questions")


def _number_in(value: Any, lower: float, upper: float) -> bool:
    return (
        type(value) in (int, float)
        and math.isfinite(float(value))
        and lower <= float(value) <= upper
    )


def _normalize_usage(usage: Any) -> dict[str, Any]:
    if type(usage) is not dict:
        raise JevError("invalid_response")

    clean: dict[str, Any] = {}
    for key in ("input_tokens", "output_tokens"):
        if key in usage:
            value = usage[key]
            if type(value) is not int or value < 0:
                raise JevError("invalid_response")
            clean[key] = value

    if "cost" in usage:
        value = usage["cost"]
        if type(value) not in (int, float) or not math.isfinite(float(value)) or value < 0:
            raise JevError("invalid_response")
        clean["cost"] = float(value)

    return clean


def _normalize_probabilities(
    probabilities: Any,
    expected_keys: set[str],
) -> dict[str, float] | None:
    if probabilities is None:
        return None
    if (
        type(probabilities) is not dict
        or set(probabilities) != expected_keys
        or not all(_number_in(value, 0, 1) for value in probabilities.values())
        or not math.isclose(
            sum(float(value) for value in probabilities.values()),
            1.0,
            rel_tol=0,
            abs_tol=0.01,
        )
    ):
        raise JevError("invalid_response")
    return {key: float(probabilities[key]) for key in probabilities}


def _normalize_answer(question: dict[str, Any], answer: Any) -> dict[str, Any]:
    if type(answer) is not dict or answer.get("type") != question["type"]:
        raise JevError("invalid_response")

    kind = question["type"]
    clean: dict[str, Any] = {"type": kind}

    if kind == "noul":
        value = answer.get("noul")
        if not _number_in(value, 0, 1):
            raise JevError("invalid_response")
        clean["noul"] = float(value)
        return clean

    confidence = answer.get("confidence")
    if confidence is not None:
        if not _number_in(confidence, 0, 1):
            raise JevError("invalid_response")
        clean["confidence"] = float(confidence)

    if kind == "choice":
        choice = answer.get("choice")
        criteria = question["criteria"]
        if not isinstance(choice, str) or choice not in criteria:
            raise JevError("invalid_response")
        clean["choice"] = choice
        probabilities = _normalize_probabilities(
            answer.get("probabilities"),
            set(criteria),
        )
        if probabilities is not None:
            clean["probabilities"] = probabilities
        return clean

    score = answer.get("score")
    criteria = question["criteria"]
    if not _number_in(score, 0, len(criteria) - 1):
        raise JevError("invalid_response")
    clean["score"] = float(score)
    probabilities = _normalize_probabilities(
        answer.get("probabilities"),
        {str(i) for i in range(len(criteria))},
    )
    if probabilities is not None:
        clean["probabilities"] = probabilities
    return clean


def _normalize_response(
    result: Any,
    questions: dict[str, Any],
) -> dict[str, Any]:
    if (
        type(result) is not dict
        or not _text(result.get("model"))
        or type(result.get("answers")) is not dict
    ):
        raise JevError("invalid_response")

    answers: dict[str, Any] = {}
    for name, question in questions.items():
        if name not in result["answers"]:
            raise JevError("invalid_response")
        answers[name] = _normalize_answer(question, result["answers"][name])

    return {
        "model": result["model"].strip(),
        "answers": answers,
        "usage": _normalize_usage(result.get("usage")),
    }


def _transport(
    url: str,
    token: str,
    body: bytes,
    timeout: float,
) -> bytes:
    """One POST with redirects and environment proxies disabled."""
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "hermes-jev-performance/0.1",
            "HTTP-Referer": "https://github.com/aiverse-filmmakers/hermes-jev-performance",
            "X-Title": "Hermes Jev Performance",
        },
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _NoRedirect(),
    )

    try:
        with opener.open(request, timeout=timeout) as response:
            length = response.headers.get("Content-Length", "")
            if length.isascii() and length.isdigit() and int(length) > MAX_RESPONSE_BYTES:
                raise JevError("response_too_large")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        raise JevError(
            "http",
            status_code=status,
            retryable=(status == 429 or status >= 500),
        ) from None
    except urllib.error.URLError as exc:
        if isinstance(getattr(exc, "reason", None), (TimeoutError, socket.timeout)):
            raise JevError("timeout", retryable=True) from None
        raise JevError("network", retryable=True) from None
    except (TimeoutError, socket.timeout):
        raise JevError("timeout", retryable=True) from None
    except OSError:
        raise JevError("network", retryable=True) from None

    if len(raw) > MAX_RESPONSE_BYTES:
        raise JevError("response_too_large")
    return raw


def evaluate(
    *,
    token: str,
    state: Any,
    questions: dict[str, Any],
    model: str = DEFAULT_JEV_MODEL,
    timeout: float = 2.5,
) -> dict[str, Any]:
    """Evaluate one Jev Decisions request through OpenRouter.

    No retries are performed. The returned object contains only normalized
    model/answer/usage metadata plus local latency and the requested model.
    """
    started = time.monotonic()

    if not isinstance(token, str) or not re.fullmatch(r"[!-~]{1,8192}", token):
        raise JevError("invalid_token")
    if (
        not isinstance(model, str)
        or not re.fullmatch(r"[a-zA-Z0-9~][a-zA-Z0-9._/@~-]{0,127}", model)
    ):
        raise JevError("invalid_model")
    if type(timeout) not in (int, float) or isinstance(timeout, bool) or not 0.1 <= float(timeout) <= 30:
        raise JevError("invalid_timeout")

    _validate_state(state)
    _validate_questions(questions)

    payload = {
        "model": model,
        "state": state,
        "questions": questions,
    }
    body = _encode_payload(payload)
    raw = _transport(
        OPENROUTER_DECISIONS_URL,
        token,
        body,
        float(timeout),
    )

    try:
        decoded = json.loads(raw)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise JevError("invalid_json") from None

    normalized = _normalize_response(decoded, questions)
    return {
        **normalized,
        "provider": "openrouter",
        "requested_model": model,
        "latency_ms": (time.monotonic() - started) * 1000,
    }


def choice_question(
    instructions: str,
    criteria: dict[str, str | None],
) -> dict[str, Any]:
    question = {
        "type": "choice",
        "instructions": instructions,
        "criteria": dict(criteria),
    }
    _validate_questions({"question": question})
    return question


def noul_question(
    instructions: str,
    criteria: dict[str, str] | None = None,
) -> dict[str, Any]:
    question: dict[str, Any] = {
        "type": "noul",
        "instructions": instructions,
    }
    if criteria is not None:
        question["criteria"] = dict(criteria)
    _validate_questions({"question": question})
    return question


def score_question(
    instructions: str,
    levels: list[str],
) -> dict[str, Any]:
    question = {
        "type": "score",
        "instructions": instructions,
        "criteria": list(levels),
    }
    _validate_questions({"question": question})
    return question
