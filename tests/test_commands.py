import unittest

from jevperf.commands import USAGE, handle_jev_command, render_status
from tests.fakes import FakeContext


class CommandTests(unittest.TestCase):
    def test_empty_command_is_status(self):
        result = handle_jev_command(FakeContext(), "")
        self.assertIn("Hermes Jev Performance", result)
        self.assertIn("Phase: 4 (routing middleware)", result)
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

    def test_help(self):
        self.assertEqual(handle_jev_command(FakeContext(), "help"), USAGE)

    def test_unknown_subcommand_returns_usage(self):
        self.assertEqual(handle_jev_command(FakeContext(), "launch"), USAGE)


if __name__ == "__main__":
    unittest.main()
