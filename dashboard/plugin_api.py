"""Dashboard backend for Hermes Jev Performance.

Mounted by Hermes at /api/plugins/hermes-jev-performance/.
The host dashboard auth gate runs before these routes.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

from fastapi import APIRouter, HTTPException, Query


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from jevperf.dashboard_service import (  # noqa: E402
    set_dashboard_mode,
    status_payload,
    summary_payload,
)


router = APIRouter()


@router.get("/status")
async def get_status() -> dict[str, Any]:
    try:
        return status_payload()
    except Exception:
        raise HTTPException(status_code=503, detail="Jev dashboard status unavailable")


@router.get("/summary")
async def get_summary(
    hours: int = Query(default=24, ge=1, le=24 * 3650),
) -> dict[str, Any]:
    try:
        return summary_payload(hours=hours)
    except Exception:
        raise HTTPException(status_code=503, detail="Jev telemetry unavailable")


@router.put("/mode")
async def update_mode(body: dict[str, Any]) -> dict[str, Any]:
    if set(body) != {"mode"}:
        raise HTTPException(status_code=422, detail="Expected exactly one field: mode")

    mode = body.get("mode")
    if not isinstance(mode, str):
        raise HTTPException(status_code=422, detail="mode must be a string")

    try:
        return set_dashboard_mode(mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Jev mode is administrator-managed")
    except RuntimeError:
        raise HTTPException(status_code=409, detail="Jev mode write could not be verified")
    except Exception:
        raise HTTPException(status_code=503, detail="Jev mode update unavailable")
