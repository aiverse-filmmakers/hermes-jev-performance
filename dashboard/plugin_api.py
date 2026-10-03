"""Bridge the combined package API mount to the canonical agent implementation."""

from __future__ import annotations

from pathlib import Path
import sys


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PLUGIN_ROOT / "agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from jevperf.plugin_api import router  # noqa: E402
