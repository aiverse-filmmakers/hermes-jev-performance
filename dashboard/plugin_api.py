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
    analytics_payload,
    benchmark_export_payload,
    benchmark_runs_payload,
    set_dashboard_mode,
    status_payload,
    summary_payload,
)


router = APIRouter()


def _ensure_profile_scope(profile: str | None) -> None:
    """Fail closed when Hermes did not scope a named-profile plugin request.

    Newer Hermes dashboard hosts scope third-party plugin API routes to the
    requested ``?profile=`` before the handler runs. Hermes 0.21.5 already has
    profile identity helpers but does not apply that request scope to plugin
    routers. Accept a named profile only when Hermes' effective HERMES_HOME
    resolves to the same profile. This preserves safe direct-profile use on the
    declared minimum while preventing cross-profile reads or writes.
    """
    requested = str(profile or "").strip()
    if not requested or requested.lower() == "current":
        return

    try:
        from hermes_cli import profiles as profiles_mod

        if not profiles_mod.profile_exists(requested):
            raise HTTPException(status_code=404, detail="Hermes profile not found")
        if not profiles_mod.profile_matches_home(requested):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Selected Hermes profile is not isolated for plugin API "
                    "requests on this host version"
                ),
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=409,
            detail="Hermes host cannot verify selected profile isolation",
        )


@router.get("/status")
async def get_status(
    profile: str | None = Query(default=None),
) -> dict[str, Any]:
    _ensure_profile_scope(profile)
    try:
        return status_payload()
    except Exception:
        raise HTTPException(status_code=503, detail="Jev dashboard status unavailable")


@router.get("/summary")
async def get_summary(
    hours: int = Query(default=24, ge=1, le=24 * 3650),
    profile: str | None = Query(default=None),
) -> dict[str, Any]:
    _ensure_profile_scope(profile)
    try:
        return summary_payload(hours=hours)
    except Exception:
        raise HTTPException(status_code=503, detail="Jev telemetry unavailable")


@router.get("/analytics")
async def get_analytics(
    hours: int = Query(default=24, ge=1, le=24 * 3650),
    limit: int = Query(default=30, ge=1, le=200),
    profile: str | None = Query(default=None),
) -> dict[str, Any]:
    _ensure_profile_scope(profile)
    try:
        return analytics_payload(hours=hours, limit=limit)
    except Exception:
        raise HTTPException(status_code=503, detail="Jev analytics unavailable")


@router.get("/benchmarks")
async def get_benchmarks(
    limit: int = Query(default=10, ge=1, le=50),
    profile: str | None = Query(default=None),
) -> dict[str, Any]:
    _ensure_profile_scope(profile)
    try:
        return benchmark_runs_payload(limit=limit)
    except Exception:
        raise HTTPException(status_code=503, detail="Jev benchmark data unavailable")


@router.get("/benchmarks/{run_id}/export")
async def get_benchmark_export(
    run_id: str,
    profile: str | None = Query(default=None),
) -> dict[str, Any]:
    _ensure_profile_scope(profile)
    try:
        return benchmark_export_payload(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Benchmark run not found")
    except Exception:
        raise HTTPException(status_code=503, detail="Benchmark export unavailable")


@router.put("/mode")
async def update_mode(
    body: dict[str, Any],
    profile: str | None = Query(default=None),
) -> dict[str, Any]:
    _ensure_profile_scope(profile)
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
