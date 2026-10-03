"""OpenRouter credential resolution for Jev.

The dedicated Jev key wins. A generic OpenRouter key is an explicit compatibility
fallback only; credentials are never copied or persisted by this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Callable, Optional


DEDICATED_OPENROUTER_SECRET = "OPENROUTER_JEV_API_TOKEN"
GENERIC_OPENROUTER_SECRET = "OPENROUTER_API_KEY"


@dataclass(frozen=True)
class Credential:
    name: str
    token: str = field(repr=False)


def _default_secret_reader(name: str) -> str:
    """Read through Hermes' profile-scoped secret API when available.

    Outside Hermes (for the explicit live smoke utility), fall back to the
    process environment. Under Hermes we intentionally do not bypass its
    secret scope by reading os.environ directly.
    """
    try:
        from agent.secret_scope import get_secret_str  # Hermes public runtime seam
    except ImportError:
        return str(os.environ.get(name, "") or "")

    try:
        return str(get_secret_str(name, "") or "")
    except Exception:
        return ""


def resolve_openrouter_credential(
    secret_reader: Optional[Callable[[str], str]] = None,
) -> Credential | None:
    """Return the first usable OpenRouter credential without exposing its value."""
    reader = secret_reader or _default_secret_reader
    for name in (DEDICATED_OPENROUTER_SECRET, GENERIC_OPENROUTER_SECRET):
        try:
            token = reader(name)
        except Exception:
            token = ""
        if isinstance(token, str) and token.strip():
            return Credential(name=name, token=token.strip())
    return None
