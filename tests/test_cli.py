import argparse
import contextlib
import io
import unittest

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
            total_jev_cost_usd = None
            avg_turn_duration_ms = None
            avg_tool_calls = None
            avg_llm_requests = None
            input_tokens = None
            output_tokens = None
            routes = ()
        return Summary()


class CliTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
