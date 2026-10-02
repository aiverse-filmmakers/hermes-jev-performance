"""Explicit live OpenRouter Jev smoke test.

This module never runs from plugin registration or CI. Running it may incur
OpenRouter charges.

Usage:
    python -m jevperf.smoke
"""

from __future__ import annotations

import json

from .client import DEFAULT_JEV_MODEL, choice_question, evaluate, safe_error_details
from .credentials import resolve_openrouter_credential


def main() -> int:
    credential = resolve_openrouter_credential()
    if credential is None:
        print(
            "No OpenRouter credential found. Configure "
            "OPENROUTER_JEV_API_TOKEN or OPENROUTER_API_KEY."
        )
        return 2

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
        details = safe_error_details(exc)
        print(json.dumps({"ok": False, **details}, indent=2, sort_keys=True))
        return 1

    answer = result["answers"]["tool_family"]
    print(json.dumps({
        "ok": True,
        "credential_source": credential.name,
        "requested_model": result["requested_model"],
        "actual_model": result["model"],
        "choice": answer["choice"],
        "confidence": answer.get("confidence"),
        "latency_ms": round(result["latency_ms"], 2),
        "usage": result["usage"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
