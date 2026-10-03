"""Resolve the installed package root for both the server and combined layouts."""

from __future__ import annotations

from pathlib import Path
import re


PLUGIN_ID = "hermes-jev-performance"
CODE_ROOT = Path(__file__).resolve().parents[1]


def _manifest_name(path: Path) -> str | None:
    try:
        text = (path / "plugin.yaml").read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"(?m)^name:\s*['\"]?([^'\"\n]+)['\"]?\s*$", text)
    return match.group(1).strip() if match else None


def plugin_root() -> Path:
    """Return the root Hermes installed, not necessarily the Python code folder."""
    if CODE_ROOT.name == "agent" and _manifest_name(CODE_ROOT.parent) == PLUGIN_ID:
        return CODE_ROOT.parent
    return CODE_ROOT


PLUGIN_ROOT = plugin_root()
