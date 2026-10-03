"""Explicit live OpenRouter Jev smoke test.

This module never runs from plugin registration or CI. Running it may incur
OpenRouter charges.

Canonical installed-plugin usage:
    hermes jev smoke

Standalone developer usage:
    OPENROUTER_JEV_API_TOKEN=<TOKEN> python -m jevperf.smoke
"""

from __future__ import annotations

import json
import os
from typing import Callable

from .client import DEFAULT_JEV_MODEL, choice_question, evaluate, safe_error_details
from .credentials import resolve_openrouter_credential


def run_smoke(
    *,
    secret_reader: Callable[[str], str] | None = None,
) -> tuple[int, dict]:
    """Make exactly one explicit Jev Decisions API call and return safe metadata."""
    credential = resolve_openrouter_credential(secret_reader)
    if credential is None:
        return 2, {
            "ok": False,
            "error": "missing_credential",
            "message": (
                "Configure OPENROUTER_JEV_API_TOKEN or OPENROUTER_API_KEY "
                "in the active Hermes profile/environment."
            ),
        }

    questions = {
        "tool_family": choice_question(
            "Which tool family best fits this request?",
            {
                "web": "Public web research or current online information.",
                "none": "No external tool is needed.",
            },
        )
    }

    try:
        result = evaluate(
            token=credential.token,
            state="Search the public web for the latest Hermes Agent release.",
            questions=questions,
            model=DEFAULT_JEV_MODEL,
        )
    except Exception as exc:
        return 1, {"ok": False, **safe_error_details(exc)}

    answer = result["answers"]["tool_family"]
    return 0, {
        "ok": True,
        "credential_source": credential.name,
        "requested_model": result["requested_model"],
        "actual_model": result["model"],
        "choice": answer["choice"],
        "confidence": answer.get("confidence"),
        "latency_ms": round(result["latency_ms"], 2),
        "usage": result["usage"],
    }


def main() -> int:
    # A standalone `python -m` process may have the Hermes codebase importable
    # without an active profile secret scope. In that developer-only path,
    # explicitly read the process environment instead of accidentally treating
    # an unscoped Hermes secret API as proof that no credential exists.
    code, payload = run_smoke(
        secret_reader=lambda name: str(os.environ.get(name, "") or ""),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
