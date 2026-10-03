#!/usr/bin/env python3
"""Batched live P1-P9 release gate for a real Hermes installation.

Safe by default:
- active Hermes profile checks are read-only;
- install/disable/enable/remove lifecycle checks use an isolated temporary HERMES_HOME;
- paid/provider calls and active-agent turns require explicit flags;
- raw command output is not persisted in the report.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
import re
import subprocess
import tempfile
from typing import Callable, Sequence


PLUGIN_ID = "hermes-jev-performance"
DEFAULT_SOURCE = "aiverse-filmmakers/hermes-jev-performance"
_FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


@dataclass(frozen=True)
class GateResult:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class Proc:
    returncode: int
    stdout: str
    stderr: str


def _run(
    argv: Sequence[str],
    *,
    env: dict[str, str] | None = None,
    timeout: float = 180.0,
) -> Proc:
    completed = subprocess.run(
        list(argv),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return Proc(completed.returncode, completed.stdout or "", completed.stderr or "")


def _safe_env(base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"
    return env


def _result(name: str, ok: bool, detail: str) -> GateResult:
    return GateResult(name, "pass" if ok else "fail", detail)


def _command_check(
    name: str,
    argv: Sequence[str],
    *,
    runner: Callable[..., Proc],
    env: dict[str, str] | None = None,
    timeout: float = 180.0,
    success_detail: str,
    failure_detail: str,
) -> GateResult:
    try:
        proc = runner(argv, env=env, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return GateResult(name, "fail", failure_detail)
    return _result(
        name,
        proc.returncode == 0,
        success_detail if proc.returncode == 0 else failure_detail,
    )


def active_profile_checks(
    *,
    runner: Callable[..., Proc] = _run,
) -> list[GateResult]:
    env = _safe_env()
    return [
        _command_check(
            "hermes_version",
            ["hermes", "--version"],
            runner=runner,
            env=env,
            success_detail="Hermes executable/version probe passed",
            failure_detail="Hermes executable/version probe failed",
        ),
        _command_check(
            "plugin_doctor",
            ["hermes", "plugins", "doctor", PLUGIN_ID, "--ci"],
            runner=runner,
            env=env,
            success_detail="Hermes native plugin doctor passed",
            failure_detail="Hermes native plugin doctor failed or plugin is not installed",
        ),
        _command_check(
            "jev_doctor",
            ["hermes", "jev", "doctor", "--json"],
            runner=runner,
            env=env,
            success_detail="Jev local doctor passed without provider calls",
            failure_detail="Jev local doctor reported a failure",
        ),
        _command_check(
            "jev_status",
            ["hermes", "jev", "status"],
            runner=runner,
            env=env,
            success_detail="Jev CLI status is registered",
            failure_detail="Jev CLI status is unavailable",
        ),
        _command_check(
            "benchmark_preview",
            ["hermes", "jev", "benchmark", "--repeats", "2", "--warmups", "0"],
            runner=runner,
            env=env,
            success_detail="Controlled benchmark preview passed with zero benchmark turns",
            failure_detail="Controlled benchmark preview failed",
        ),
    ]


def isolated_lifecycle_checks(
    *,
    source: str,
    ref: str,
    runner: Callable[..., Proc] = _run,
) -> list[GateResult]:
    if not _FULL_SHA.fullmatch(ref or ""):
        return [
            GateResult(
                "isolated_lifecycle",
                "fail",
                "a full 40-character commit SHA is required for reproducible lifecycle validation",
            )
        ]

    results: list[GateResult] = []
    with tempfile.TemporaryDirectory(prefix="hermes-jev-gate-") as temp:
        env = _safe_env()
        env["HERMES_HOME"] = temp

        initial_steps = [
            (
                "clean_install",
                [
                    "hermes", "plugins", "install", source,
                    "--enable", "--ref", ref,
                ],
                "isolated clean install and enable passed",
                "isolated clean install failed",
                300.0,
            ),
            (
                "isolated_plugin_doctor",
                ["hermes", "plugins", "doctor", PLUGIN_ID, "--ci"],
                "isolated Hermes plugin doctor passed",
                "isolated Hermes plugin doctor failed",
                180.0,
            ),
            (
                "isolated_status",
                ["hermes", "jev", "status"],
                "isolated Jev CLI loaded",
                "isolated Jev CLI did not load",
                180.0,
            ),
            (
                "disable",
                ["hermes", "plugins", "disable", PLUGIN_ID],
                "isolated disable passed",
                "isolated disable failed",
                180.0,
            ),
        ]

        for name, argv, ok_detail, bad_detail, timeout in initial_steps:
            result = _command_check(
                name,
                argv,
                runner=runner,
                env=env,
                timeout=timeout,
                success_detail=ok_detail,
                failure_detail=bad_detail,
            )
            results.append(result)
            if result.status == "fail" and name == "clean_install":
                return results

        # A disabled plugin must not keep its custom CLI registration active.
        try:
            disabled_status = runner(
                ["hermes", "jev", "status"],
                env=env,
                timeout=180.0,
            )
        except (OSError, subprocess.SubprocessError):
            results.append(
                GateResult("disabled_registration_absent", "pass", "Jev CLI absent while plugin disabled")
            )
        else:
            results.append(
                _result(
                    "disabled_registration_absent",
                    disabled_status.returncode != 0,
                    "Jev CLI absent while plugin disabled"
                    if disabled_status.returncode != 0
                    else "Jev CLI remained active after plugin disable",
                )
            )

        results.append(
            _command_check(
                "enable",
                ["hermes", "plugins", "enable", PLUGIN_ID],
                runner=runner,
                env=env,
                success_detail="isolated re-enable passed",
                failure_detail="isolated re-enable failed",
            )
        )
        results.append(
            _command_check(
                "post_enable_status",
                ["hermes", "jev", "status"],
                runner=runner,
                env=env,
                success_detail="Jev CLI restored after re-enable",
                failure_detail="Jev CLI unavailable after re-enable",
            )
        )

        # Mode persistence is tested only inside the isolated profile.
        for mode in ("off", "shadow", "on", "shadow"):
            results.append(
                _command_check(
                    f"isolated_mode_{mode}",
                    ["hermes", "jev", mode],
                    runner=runner,
                    env=env,
                    success_detail=f"isolated mode switch to {mode} passed",
                    failure_detail=f"isolated mode switch to {mode} failed",
                )
            )

        results.append(
            _command_check(
                "remove",
                ["hermes", "plugins", "remove", PLUGIN_ID],
                runner=runner,
                env=env,
                timeout=180.0,
                success_detail="isolated plugin removal passed",
                failure_detail="isolated plugin removal failed",
            )
        )

        try:
            listing = runner(
                ["hermes", "plugins", "list"],
                env=env,
                timeout=180.0,
            )
        except (OSError, subprocess.SubprocessError):
            results.append(
                GateResult("post_remove_absence", "fail", "could not verify isolated plugin list")
            )
        else:
            absent = listing.returncode == 0 and PLUGIN_ID not in listing.stdout
            results.append(
                _result(
                    "post_remove_absence",
                    absent,
                    "plugin absent after isolated removal"
                    if absent
                    else "plugin still appears after isolated removal",
                )
            )

    return results


def live_jev_smoke(
    *,
    runner: Callable[..., Proc] = _run,
) -> GateResult:
    return _command_check(
        "live_openrouter_jev",
        ["hermes", "jev", "smoke"],
        runner=runner,
        env=_safe_env(),
        timeout=60.0,
        success_detail="explicit profile-scoped OpenRouter Jev smoke call passed",
        failure_detail="explicit profile-scoped OpenRouter Jev smoke call failed",
    )


def active_agent_smoke(
    *,
    runner: Callable[..., Proc] = _run,
) -> list[GateResult]:
    """Explicit paid/current-profile smoke turns. Original mode is restored."""
    env = _safe_env()
    try:
        status = runner(["hermes", "jev", "status"], env=env, timeout=60.0)
    except (OSError, subprocess.SubprocessError):
        return [GateResult("active_agent_smoke", "fail", "could not read current Jev mode")]

    match = re.search(r"(?mi)^Mode:\s*(off|shadow|on)\s*$", status.stdout)
    if status.returncode != 0 or match is None:
        return [GateResult("active_agent_smoke", "fail", "could not determine current Jev mode")]

    original = match.group(1).lower()
    results: list[GateResult] = []
    prompts = {
        "off": "Explain recursion in one sentence.",
        "shadow": "Check how much RAM this machine is currently using.",
        "on": "Search the public web for the official Hermes Agent repository and return its name.",
    }

    try:
        for mode in ("off", "shadow", "on"):
            switched = runner(["hermes", "jev", mode], env=env, timeout=60.0)
            if switched.returncode != 0:
                results.append(GateResult(f"agent_{mode}", "fail", f"could not switch to {mode}"))
                continue
            try:
                proc = runner(
                    ["hermes", "chat", "--oneshot", "-q", prompts[mode]],
                    env=env,
                    timeout=240.0,
                )
            except (OSError, subprocess.SubprocessError):
                results.append(GateResult(f"agent_{mode}", "fail", f"{mode} Hermes turn failed"))
            else:
                results.append(
                    _result(
                        f"agent_{mode}",
                        proc.returncode == 0,
                        f"{mode} Hermes turn completed"
                        if proc.returncode == 0
                        else f"{mode} Hermes turn failed",
                    )
                )
    finally:
        try:
            runner(["hermes", "jev", original], env=env, timeout=60.0)
        except Exception:
            results.append(
                GateResult(
                    "restore_original_mode",
                    "fail",
                    "could not restore the original active-profile Jev mode",
                )
            )
        else:
            results.append(
                GateResult(
                    "restore_original_mode",
                    "pass",
                    f"restored original mode {original}",
                )
            )

    return results


def report_payload(results: list[GateResult]) -> dict:
    counts = {
        status: sum(1 for result in results if result.status == status)
        for status in ("pass", "warn", "fail", "manual")
    }
    overall = "fail" if counts["fail"] else ("manual" if counts["manual"] else "pass")
    return {
        "format": "hermes-jev-live-release-gate-v1",
        "overall": overall,
        "counts": counts,
        "results": [asdict(result) for result in results],
        "privacy": {
            "raw_command_output_included": False,
            "prompt_content_included": False,
            "credentials_included": False,
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run batched P1-P9 live release checks for Hermes Jev Performance."
    )
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument(
        "--ref",
        default="",
        help="Full 40-character commit SHA for isolated lifecycle testing.",
    )
    parser.add_argument(
        "--lifecycle",
        action="store_true",
        help="Run clean install/disable/re-enable/remove in an isolated temporary HERMES_HOME.",
    )
    parser.add_argument(
        "--live-jev",
        action="store_true",
        help="Make one explicit profile-scoped OpenRouter Jev smoke call. May incur provider cost.",
    )
    parser.add_argument(
        "--active-agent",
        action="store_true",
        help="Run three real Hermes turns in OFF/SHADOW/ON on the active profile and restore the original mode.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    results = active_profile_checks()
    if args.lifecycle:
        results.extend(
            isolated_lifecycle_checks(
                source=args.source,
                ref=args.ref,
            )
        )
    if args.live_jev:
        results.append(live_jev_smoke())
    if args.active_agent:
        results.extend(active_agent_smoke())

    results.extend(
        [
            GateResult(
                "telegram_gateway",
                "manual",
                "send /jev status and /jev doctor through the real Telegram gateway",
            ),
            GateResult(
                "dashboard_ui",
                "manual",
                "open Hermes dashboard and verify the Jev Performance tab plus mode read-back",
            ),
        ]
    )

    report = report_payload(results)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("Hermes Jev live release gate")
        print(f"Overall: {report['overall'].upper()}")
        for result in results:
            print(f"[{result.status.upper()}] {result.name}: {result.detail}")
        print(
            "Summary: "
            f"{report['counts']['pass']} pass, "
            f"{report['counts']['fail']} fail, "
            f"{report['counts']['manual']} manual"
        )

    return 1 if report["counts"]["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
