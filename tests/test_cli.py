import argparse
import contextlib
import io
import unittest
from unittest import mock

from jevperf.cli import build_cli
from tests.fakes import FakeContext


class FakeTelemetry:
    def __init__(self):
        self.mode_changes = []

    def record_mode_change(self, old_mode, new_mode, *, source):
        self.mode_changes.append((old_mode, new_mode, source))

    def summary(self, since_hours=24):
        class Summary:
            decisions = 0
            turns = 0
            applied = 0
            fallback = 0
            avg_confidence = None
            avg_jev_latency_ms = None
            p50_jev_latency_ms = None
            p95_jev_latency_ms = None
            avg_jev_cost_usd = None
            total_jev_cost_usd = None
            avg_turn_duration_ms = None
            avg_tool_calls = None
            avg_llm_requests = None
            input_tokens = None
            output_tokens = None
            routes = ()
        return Summary()


class CliTests(unittest.TestCase):
    def test_missing_optional_benchmark_suite_gives_actionable_preview_error(self):
        code, output, _, _ = self.parse_and_run(['benchmark', '--fixtures', '/synthetic-not-present/suite.json'])
        self.assertEqual(code, 2)
        self.assertIn('--fixtures PATH', output)
        self.assertIn('not installed', output)

    def parse_and_run(self, argv, ctx=None, telemetry=None):
        ctx = ctx or FakeContext()
        telemetry = telemetry or FakeTelemetry()
        parser = argparse.ArgumentParser()
        setup, handler = build_cli(ctx, None, telemetry)
        setup(parser)
        args = parser.parse_args(argv)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = handler(args)
        return code, output.getvalue(), ctx, telemetry

    def test_cli_off_persists_mode(self):
        code, output, ctx, telemetry = self.parse_and_run(
            ["off"],
            ctx=FakeContext({"mode": "shadow"}),
        )
        self.assertEqual(code, 0)
        self.assertEqual(ctx.settings["mode"], "off")
        self.assertIn("Jev routing: OFF", output)
        self.assertEqual(telemetry.mode_changes, [("shadow", "off", "cli")])

    def test_cli_notice(self):
        code, output, ctx, _ = self.parse_and_run(["notice", "on"])
        self.assertEqual(code, 0)
        self.assertTrue(ctx.settings["notice"])
        self.assertIn("Jev reply notice: ON", output)

    def test_cli_defaults_to_status(self):
        code, output, _, _ = self.parse_and_run([])
        self.assertEqual(code, 0)
        self.assertIn("Hermes Jev Performance", output)

    def test_cli_smoke_uses_explicit_live_smoke_helper(self):
        payload = {
            "ok": True,
            "credential_source": "OPENROUTER_JEV_API_TOKEN",
            "choice": "web",
        }
        with mock.patch("jevperf.cli.run_smoke", return_value=(0, payload)) as smoke:
            code, output, _, _ = self.parse_and_run(["smoke"])
        self.assertEqual(code, 0)
        smoke.assert_called_once_with()
        self.assertIn('"ok": true', output)
        self.assertNotIn("fixture-token", output)

    def test_cli_smoke_propagates_safe_failure_code(self):
        with mock.patch(
            "jevperf.cli.run_smoke",
            return_value=(2, {"ok": False, "error": "missing_credential"}),
        ):
            code, output, _, _ = self.parse_and_run(["smoke"])
        self.assertEqual(code, 2)
        self.assertIn("missing_credential", output)

    def test_benchmark_preview_never_runs_live_harness(self):
        with mock.patch(
            "jevperf.cli.run_live_benchmark",
            side_effect=AssertionError("live benchmark must not run"),
        ):
            code, output, _, _ = self.parse_and_run([
                "benchmark",
                "--repeats",
                "2",
                "--warmups",
                "0",
            ])
        self.assertEqual(code, 0)
        self.assertIn("Controlled Jev benchmark preview", output)
        self.assertIn("No benchmark was run", output)
        self.assertIn("Measured repeats: 2", output)

    def test_cli_doctor_renders_safe_report(self):
        report = {
            "plugin": "hermes-jev-performance",
            "version": "test",
            "overall": "pass",
            "counts": {"pass": 1, "warn": 0, "fail": 0},
            "checks": [
                {"name": "configuration", "status": "pass", "detail": "ok"},
            ],
            "network_calls": 0,
            "secrets_printed": False,
        }
        with mock.patch("jevperf.cli.run_doctor", return_value=report):
            code, output, _, _ = self.parse_and_run(["doctor"])
        self.assertEqual(code, 0)
        self.assertIn("Hermes Jev Performance doctor", output)
        self.assertIn("Network calls: 0", output)

    def test_cli_doctor_json_is_machine_readable(self):
        report = {
            "plugin": "hermes-jev-performance",
            "version": "test",
            "overall": "warn",
            "counts": {"pass": 1, "warn": 1, "fail": 0},
            "checks": [],
            "network_calls": 0,
            "secrets_printed": False,
        }
        with mock.patch("jevperf.cli.run_doctor", return_value=report):
            code, output, _, _ = self.parse_and_run(["doctor", "--json"])
        self.assertEqual(code, 0)
        self.assertIn('"overall": "warn"', output)


if __name__ == "__main__":
    unittest.main()
