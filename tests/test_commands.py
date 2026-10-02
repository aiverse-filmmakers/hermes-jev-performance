import unittest

from jevperf.commands import (
    USAGE,
    handle_jev_command,
    render_status,
)
from tests.fakes import FakeContext


class FakeStats:
    decisions = 5
    turns = 4
    applied = 3
    fallback = 2
    avg_confidence = 0.91
    avg_jev_latency_ms = 412.3
    total_jev_cost_usd = 0.000061
    avg_turn_duration_ms = 14250
    avg_tool_calls = 2.5
    avg_llm_requests = 1.75
    input_tokens = 12000
    output_tokens = 1600
    routes = (("web", 3), ("terminal", 2))


class FakeTelemetry:
    def __init__(self):
        self.mode_changes = []

    def summary(self, since_hours=24):
        self.since_hours = since_hours
        return FakeStats()

    def record_mode_change(self, old_mode, new_mode, *, source):
        self.mode_changes.append((old_mode, new_mode, source))


class CommandTests(unittest.TestCase):
    def test_empty_command_is_status(self):
        result = handle_jev_command(FakeContext(), "")
        self.assertIn("Hermes Jev Performance", result)
        self.assertIn("Phase: 9 (hardening + packaging)", result)
        self.assertIn("Last route: none yet", result)

    def test_status_does_not_expose_unknown_settings_or_secrets(self):
        ctx = FakeContext({
            "mode": "shadow",
            "api_key": "DO_NOT_PRINT_ME",
            "token": "DO_NOT_PRINT_ME_EITHER",
        })
        result = render_status(ctx)
        self.assertNotIn("DO_NOT_PRINT_ME", result)
        self.assertNotIn("api_key", result)
        self.assertNotIn("token", result.lower())

    def test_mode_commands_persist_immediately(self):
        telemetry = FakeTelemetry()
        ctx = FakeContext({"mode": "shadow"})

        self.assertEqual(
            handle_jev_command(ctx, "on", telemetry=telemetry),
            "Jev routing: ON",
        )
        self.assertEqual(ctx.settings["mode"], "on")

        self.assertEqual(
            handle_jev_command(ctx, "off", telemetry=telemetry),
            "Jev routing: OFF",
        )
        self.assertEqual(ctx.settings["mode"], "off")

        self.assertEqual(
            handle_jev_command(ctx, "shadow", telemetry=telemetry),
            "Jev routing: SHADOW",
        )
        self.assertEqual(ctx.settings["mode"], "shadow")
        self.assertEqual(
            telemetry.mode_changes,
            [
                ("shadow", "on", "slash"),
                ("on", "off", "slash"),
                ("off", "shadow", "slash"),
            ],
        )

    def test_notice_commands_persist(self):
        ctx = FakeContext()
        self.assertEqual(
            handle_jev_command(ctx, "notice on"),
            "Jev reply notice: ON",
        )
        self.assertTrue(ctx.settings["notice"])
        self.assertEqual(
            handle_jev_command(ctx, "notice off"),
            "Jev reply notice: OFF",
        )
        self.assertFalse(ctx.settings["notice"])

    def test_stats_is_concise_and_uses_24_hours(self):
        telemetry = FakeTelemetry()
        result = handle_jev_command(FakeContext(), "stats", telemetry=telemetry)
        self.assertEqual(telemetry.since_hours, 24)
        self.assertIn("Jev decisions: 5", result)
        self.assertIn("Avg Jev latency: 412ms", result)
        self.assertIn("Jev cost: $0.000061", result)
        self.assertIn("Routes: web:3, terminal:2", result)

    def test_setting_failure_is_explicit(self):
        ctx = FakeContext(set_config=False)
        result = handle_jev_command(ctx, "off")
        self.assertIn("could not be changed", result)

    def test_doctor_command_is_safe(self):
        result = handle_jev_command(FakeContext(), "doctor")
        self.assertIn("Hermes Jev Performance doctor", result)
        self.assertIn("Network calls: 0", result)

    def test_help(self):
        self.assertEqual(handle_jev_command(FakeContext(), "help"), USAGE)

    def test_unknown_subcommand_returns_usage(self):
        self.assertEqual(handle_jev_command(FakeContext(), "launch"), USAGE)


if __name__ == "__main__":
    unittest.main()
