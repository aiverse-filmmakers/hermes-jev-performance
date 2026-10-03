"""Top-level `hermes jev ...` operator controls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .benchmark_export import write_anonymized_export
from .benchmark_runner import benchmark_plan_summary, run_live_benchmark
from .commands import render_stats, render_status, set_mode, set_notice
from .doctor import render_doctor, run_doctor
from .smoke import run_smoke


def _fmt_delta(metric: dict[str, Any]) -> str:
    off = metric.get("off_mean")
    on = metric.get("on_mean")
    pct = metric.get("percent_change")
    if off is None or on is None:
        return "unavailable"
    pct_text = "n/a" if pct is None else f"{float(pct):+.1f}%"
    return f"OFF {float(off):.2f} -> ON {float(on):.2f} ({pct_text})"


def build_cli(ctx: Any, router_middleware: Any, telemetry: Any):
    def setup(parser: argparse.ArgumentParser) -> None:
        sub = parser.add_subparsers(dest="jev_action")

        sub.add_parser("status", help="Show Jev routing status.")
        sub.add_parser("on", help="Enable Jev routing.")
        sub.add_parser("off", help="Disable Jev routing.")
        sub.add_parser("shadow", help="Run Jev decisions without changing Hermes tools.")
        sub.add_parser("stats", help="Show local Jev/Hermes performance stats.")
        sub.add_parser(
            "smoke",
            help="Explicitly make one live OpenRouter Jev Decisions API call.",
        )

        doctor = sub.add_parser("doctor", help="Run local Jev diagnostics without network calls.")
        doctor.add_argument("--json", action="store_true", help="Print machine-readable diagnostic JSON.")
        doctor.add_argument(
            "--repair-db",
            action="store_true",
            help="Quarantine a corrupt local metrics DB and create a clean schema.",
        )

        notice = sub.add_parser("notice", help="Control concise reply notices.")
        notice.add_argument("state", choices=("on", "off"))

        benchmark = sub.add_parser(
            "benchmark",
            help="Preview or explicitly run the controlled read-only OFF-vs-ON benchmark.",
        )
        benchmark.add_argument(
            "--live",
            action="store_true",
            help="Actually run Hermes/OpenRouter benchmark turns. Without this flag only the plan is shown.",
        )
        benchmark.add_argument("--repeats", type=int, default=3)
        benchmark.add_argument("--warmups", type=int, default=1)
        benchmark.add_argument(
            "--include-network",
            action="store_true",
            help="Include the optional public-web read-only fixture.",
        )
        benchmark.add_argument("--timeout", type=float, default=180.0)
        benchmark.add_argument(
            "--export",
            type=str,
            default=None,
            help="Write anonymized benchmark JSON after a live run.",
        )

    def handler(args: argparse.Namespace) -> int:
        action = str(getattr(args, "jev_action", "") or "status").lower()

        if action == "status":
            print(render_status(ctx, router_middleware))
            return 0
        if action in {"on", "off", "shadow"}:
            print(set_mode(ctx, action, telemetry, source="cli"))
            return 0
        if action == "stats":
            print(render_stats(telemetry))
            return 0
        if action == "smoke":
            code, payload = run_smoke()
            print(json.dumps(payload, indent=2, sort_keys=True))
            return code
        if action == "doctor":
            report = run_doctor(
                ctx,
                repair_db=bool(getattr(args, "repair_db", False)),
            )
            if bool(getattr(args, "json", False)):
                print(json.dumps(report, sort_keys=True))
            else:
                print(render_doctor(report))
            return 1 if report.get("overall") == "fail" else 0
        if action == "notice":
            state = str(getattr(args, "state", "") or "").lower()
            print(set_notice(ctx, state == "on"))
            return 0
        if action == "benchmark":
            repeats = int(getattr(args, "repeats", 3))
            warmups = int(getattr(args, "warmups", 1))
            include_network = bool(getattr(args, "include_network", False))
            try:
                plan = benchmark_plan_summary(
                    repeats=repeats,
                    warmups=warmups,
                    include_network=include_network,
                )
            except ValueError as exc:
                print(f"Benchmark configuration error: {exc}")
                return 2
            if not bool(getattr(args, "live", False)):
                print("Controlled Jev benchmark preview")
                print(f"Fixtures: {plan['fixture_count']} ({', '.join(plan['fixtures'])})")
                print(f"Warmups: {plan['warmups']} per fixture/mode")
                print(f"Measured repeats: {plan['repeats']}")
                print(f"Total Hermes turns: {plan['total_turns']}")
                print(f"Measured turns: {plan['measured_turns']}")
                print(f"Public-web workload fixture: {'included' if plan['public_web_fixture_included'] else 'excluded'}")
                print("Order: paired alternating OFF/ON")
                print("No benchmark was run. Add --live to execute paid/local Hermes turns.")
                return 0

            try:
                report = run_live_benchmark(
                    ctx,
                    telemetry,
                    repeats=repeats,
                    warmups=warmups,
                    include_network=include_network,
                    timeout_seconds=float(getattr(args, "timeout", 180.0)),
                )
            except (ValueError, RuntimeError) as exc:
                print(f"Benchmark failed: {exc}")
                return 2
            except Exception:
                print("Benchmark failed: unexpected runner error")
                return 2
            run = report["run"]
            comparison = report["comparison"]
            print(f"Benchmark run: {run['run_id']}")
            print(f"Status: {run['status']}")
            print(f"Matched pairs: {comparison['matched_pairs']}")
            print(f"Invalid ON routing samples: {comparison['invalid_routing_samples']['on']}")
            for key, label in (
                ("hermes_duration_ms", "Hermes duration"),
                ("tool_calls", "Tool calls"),
                ("llm_requests", "LLM requests"),
                ("total_tokens", "Total tokens"),
            ):
                print(f"{label}: {_fmt_delta(comparison['metrics'][key])}")

            export_path = getattr(args, "export", None)
            if export_path:
                store = telemetry.stores.get()
                written = write_anonymized_export(
                    store,
                    run["run_id"],
                    Path(export_path),
                )
                print(f"Export: {written}")
            return 0

        print("Usage: hermes jev {status|on|off|shadow|stats|smoke|doctor|notice|benchmark}")
        return 2

    return setup, handler
