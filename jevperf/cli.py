"""Top-level `hermes jev ...` operator controls."""

from __future__ import annotations

import argparse
from typing import Any

from .commands import render_stats, render_status, set_mode, set_notice


def build_cli(ctx: Any, router_middleware: Any, telemetry: Any):
    def setup(parser: argparse.ArgumentParser) -> None:
        sub = parser.add_subparsers(dest="jev_action")

        sub.add_parser("status", help="Show Jev routing status.")
        sub.add_parser("on", help="Enable Jev routing.")
        sub.add_parser("off", help="Disable Jev routing.")
        sub.add_parser("shadow", help="Run Jev decisions without changing Hermes tools.")
        sub.add_parser("stats", help="Show local Jev/Hermes performance stats.")

        notice = sub.add_parser("notice", help="Control concise reply notices.")
        notice.add_argument("state", choices=("on", "off"))

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
        if action == "notice":
            state = str(getattr(args, "state", "") or "").lower()
            print(set_notice(ctx, state == "on"))
            return 0

        print("Usage: hermes jev {status|on|off|shadow|stats|notice}")
        return 2

    return setup, handler
