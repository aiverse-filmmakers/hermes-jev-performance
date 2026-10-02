import unittest

from jevperf.compatibility import detect_compatibility
from tests.fakes import FakeContext


class CompatibilityTests(unittest.TestCase):
    def test_full_fake_context(self):
        result = detect_compatibility(FakeContext())
        self.assertTrue(result["phase1_supported"])
        self.assertTrue(result["routing_surface_ready"])
        self.assertTrue(result["persistent_settings_ready"])
        self.assertTrue(result["telemetry_hooks_ready"])
        self.assertTrue(result["cli_controls_ready"])
        self.assertTrue(result["state_available"])

    def test_feature_detection_degrades(self):
        result = detect_compatibility(
            FakeContext(
                middleware=False,
                set_config=False,
                hooks=False,
                cli=False,
                state=False,
            )
        )
        self.assertTrue(result["phase1_supported"])
        self.assertFalse(result["routing_surface_ready"])
        self.assertFalse(result["persistent_settings_ready"])
        self.assertFalse(result["telemetry_hooks_ready"])
        self.assertFalse(result["cli_controls_ready"])
        self.assertFalse(result["state_available"])


if __name__ == "__main__":
    unittest.main()
