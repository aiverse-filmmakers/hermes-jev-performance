"""Non-destructive diagnostics and explicit telemetry DB repair."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable

from . import __version__
from .benchmark import load_fixture_suite
from .benchmark_runner import DEFAULT_FIXTURE_PATH
from .compatibility import (
    MIN_HERMES_VERSION,
    SUPPORTED_PYTHON_MAX,
    SUPPORTED_PYTHON_MIN,
    detect_compatibility,
    detect_hermes_version,
    version_meets_floor,
)
from .config import read_config
from .compaction_config import read_compaction_config
from .credentials import resolve_openrouter_credential
from .store import (
    SCHEMA_VERSION,
    default_db_path,
    inspect_database,
    repair_corrupt_database,
)


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    detail: str


def _check(name: str, status: str, detail: str) -> DoctorCheck:
    return DoctorCheck(name=name, status=status, detail=detail)


def _manifest_version(root: Path) -> str | None:
    path = root / "plugin.yaml"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"(?m)^version:\s*[\"']?([^\s\"']+)", text)
    return match.group(1) if match else None


def _dashboard_check(root: Path) -> DoctorCheck:
    required = (
        root / "dashboard" / "manifest.json",
        root / "dashboard" / "plugin_api.py",
        root / "dashboard" / "dist" / "index.js",
        root / "dashboard" / "dist" / "style.css",
    )
    missing = [path.relative_to(root).as_posix() for path in required if not path.is_file()]
    if missing:
        return _check("dashboard_assets", "fail", "missing: " + ", ".join(missing))
    try:
        manifest = json.loads(required[0].read_text(encoding="utf-8"))
    except Exception:
        return _check("dashboard_assets", "fail", "dashboard manifest is unreadable")
    if manifest.get("name") != "hermes-jev-performance":
        return _check("dashboard_assets", "fail", "dashboard manifest plugin id mismatch")
    return _check("dashboard_assets", "pass", "manifest, backend and pre-built assets present")


def _fixture_check(path: Path) -> DoctorCheck:
    try:
        local = load_fixture_suite(path, include_network=False)
        with_network = load_fixture_suite(path, include_network=True)
    except Exception:
        return _check("benchmark_fixtures", "fail", "read-only benchmark fixture suite is invalid")
    public_web_count = max(0, len(with_network) - len(local))
    return _check(
        "benchmark_fixtures",
        "pass",
        f"{len(local)} local read-only workload fixture(s), {public_web_count} optional public-web fixture(s)",
    )


def _python_check() -> DoctorCheck:
    current = sys.version_info[:2]
    if SUPPORTED_PYTHON_MIN <= current <= SUPPORTED_PYTHON_MAX:
        return _check(
            "python",
            "pass",
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} is in tested range",
        )
    return _check(
        "python",
        "warn",
        (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} "
            f"is outside tested {SUPPORTED_PYTHON_MIN[0]}.{SUPPORTED_PYTHON_MIN[1]}-"
            f"{SUPPORTED_PYTHON_MAX[0]}.{SUPPORTED_PYTHON_MAX[1]}"
        ),
    )


def run_doctor(
    ctx: Any,
    *,
    plugin_root: Path | str = PLUGIN_ROOT,
    db_path: Path | str | None = None,
    secret_reader: Callable[[str], str] | None = None,
    repair_db: bool = False,
) -> dict[str, Any]:
    """Run bounded local checks. No provider/network call is made."""
    root = Path(plugin_root)
    checks: list[DoctorCheck] = []
    config = read_config(ctx)
    compat = detect_compatibility(ctx)

    level = str(compat["level"])
    checks.append(
        _check(
            "hermes_plugin_api",
            "pass" if level == "supported" else ("warn" if level == "degraded" else "fail"),
            (
                f"{level}; requires Hermes >= {MIN_HERMES_VERSION}; "
                f"routing={'yes' if compat['routing_surface_ready'] else 'no'}, "
                f"hooks={'yes' if compat['telemetry_hooks_ready'] else 'no'}, "
                f"cli={'yes' if compat['cli_controls_ready'] else 'no'}"
            ),
        )
    )

    hermes_version = detect_hermes_version()
    meets_floor = version_meets_floor(hermes_version)
    if hermes_version is None:
        checks.append(
            _check(
                "hermes_version",
                "warn",
                "version identity unavailable; feature detection remains authoritative",
            )
        )
    elif meets_floor is False:
        checks.append(
            _check(
                "hermes_version",
                "fail",
                f"{hermes_version} is below required {MIN_HERMES_VERSION}",
            )
        )
    else:
        checks.append(
            _check(
                "hermes_version",
                "pass" if meets_floor is True else "warn",
                (
                    f"{hermes_version} meets required >= {MIN_HERMES_VERSION}"
                    if meets_floor is True
                    else f"{hermes_version}; unable to parse against required {MIN_HERMES_VERSION}"
                ),
            )
        )

    checks.append(_python_check())
    compaction = read_compaction_config(ctx)
    engine_surface = callable(getattr(ctx, "register_context_engine", None))
    checks.append(_check(
        "compaction_engine", "pass" if compaction.mode == "off" or engine_surface else "warn",
        f"experimental mode={compaction.mode}; native registration={'available' if engine_surface else 'unavailable'}; "
        "activation also requires context.engine: hermes-jev-performance and agent restart",
    ))
    if compaction.warnings:
        checks.append(_check("compaction_configuration", "warn", ", ".join(compaction.warnings)))

    manifest = root / "plugin.yaml"
    manifest_version = _manifest_version(root)
    if not manifest.is_file():
        checks.append(_check("plugin_manifest", "fail", "plugin.yaml is missing"))
    elif manifest_version != __version__:
        checks.append(
            _check(
                "plugin_manifest",
                "fail",
                f"manifest version {manifest_version or 'unknown'} != runtime {__version__}",
            )
        )
    else:
        checks.append(_check("plugin_manifest", "pass", f"version {__version__}"))

    if config.warnings:
        checks.append(
            _check("configuration", "warn", "fallbacks: " + ", ".join(config.warnings))
        )
    elif config.provider != "openrouter":
        checks.append(
            _check("configuration", "fail", f"unsupported v1 provider: {config.provider}")
        )
    else:
        checks.append(
            _check(
                "configuration",
                "pass",
                f"mode={config.mode}, provider={config.provider}, telemetry={'on' if config.telemetry_enabled else 'off'}",
            )
        )

    credential = resolve_openrouter_credential(secret_reader)
    checks.append(
        _check(
            "openrouter_credential",
            "pass" if credential is not None else "warn",
            (
                f"present via {credential.name}"
                if credential is not None
                else "not found; OFF mode still works, SHADOW/ON Jev calls will fail open"
            ),
        )
    )

    checks.append(_dashboard_check(root))
    checks.append(_fixture_check(Path(DEFAULT_FIXTURE_PATH if root == PLUGIN_ROOT else root / "benchmarks" / "fixtures" / "readonly_local.json")))

    active_db_path = Path(db_path) if db_path is not None else default_db_path()
    db = inspect_database(active_db_path)
    if db["state"] == "missing":
        parent = active_db_path.parent
        existing = parent
        while not existing.exists() and existing != existing.parent:
            existing = existing.parent
        writable = os.access(existing, os.W_OK)
        checks.append(
            _check(
                "telemetry_database",
                "pass" if writable else "warn",
                "not created yet; parent storage is writable" if writable else "not created yet; storage writability unavailable",
            )
        )
    elif db["state"] == "ready":
        version = db.get("schema_version")
        status = "pass" if version == SCHEMA_VERSION else "warn"
        checks.append(
            _check(
                "telemetry_database",
                status,
                f"SQLite quick_check ok; schema={version}, runtime={SCHEMA_VERSION}",
            )
        )
    else:
        detail = "SQLite database is unreadable/corrupt"
        if repair_db:
            result = repair_corrupt_database(active_db_path)
            detail = (
                "corrupt database quarantined and a clean schema created"
                if result["repaired"]
                else "database repair could not be completed"
            )
            checks.append(
                _check(
                    "telemetry_database",
                    "pass" if result["repaired"] else "fail",
                    detail,
                )
            )
        else:
            checks.append(
                _check(
                    "telemetry_database",
                    "fail",
                    detail + "; rerun CLI doctor with --repair-db to quarantine and recreate it",
                )
            )

    counts = {
        status: sum(1 for check in checks if check.status == status)
        for status in ("pass", "warn", "fail")
    }
    overall = "fail" if counts["fail"] else ("warn" if counts["warn"] else "pass")
    return {
        "plugin": "hermes-jev-performance",
        "version": __version__,
        "overall": overall,
        "counts": counts,
        "checks": [asdict(check) for check in checks],
        "network_calls": 0,
        "secrets_printed": False,
    }


def render_doctor(report: dict[str, Any]) -> str:
    lines = [
        "Hermes Jev Performance doctor",
        f"Overall: {str(report.get('overall', 'unknown')).upper()}",
    ]
    symbol = {"pass": "OK", "warn": "WARN", "fail": "FAIL"}
    for check in report.get("checks", []):
        status = str(check.get("status", "warn"))
        lines.append(
            f"[{symbol.get(status, 'WARN')}] {check.get('name', 'check')}: {check.get('detail', '')}"
        )
    lines.append("Network calls: 0")
    return "\n".join(lines)
