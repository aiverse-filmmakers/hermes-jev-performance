import unittest
from unittest import mock

from jevperf.compatibility import (
    MIN_HERMES_VERSION,
    detect_compatibility,
    parse_semver,
    version_meets_floor,
)
from tests.fakes import FakeContext


class CompatibilityMatrixTests(unittest.TestCase):
    def test_semver_floor(self):
        self.assertEqual(MIN_HERMES_VERSION, "0.21.5")
        self.assertEqual(parse_semver("0.21.5+5301.gabc"), (0, 21, 5))
        self.assertTrue(version_meets_floor("0.21.5"))
        self.assertTrue(version_meets_floor("0.22.0"))
        self.assertFalse(version_meets_floor("0.21.4"))
        self.assertIsNone(version_meets_floor("development"))

    def test_full_public_surface_is_supported(self):
        with mock.patch("jevperf.compatibility.detect_hermes_version", return_value="0.21.5"):
            result = detect_compatibility(FakeContext())
        self.assertEqual(result["level"], "supported")
        self.assertTrue(result["routing_surface_ready"])
        self.assertTrue(result["telemetry_hooks_ready"])
        self.assertTrue(result["persistent_settings_ready"])
        self.assertTrue(result["version_meets_floor"])

    def test_below_declared_floor_is_unsupported(self):
        with mock.patch("jevperf.compatibility.detect_hermes_version", return_value="0.21.4"):
            result = detect_compatibility(FakeContext())
        self.assertEqual(result["level"], "unsupported")
        self.assertFalse(result["version_meets_floor"])

    def test_unknown_version_uses_feature_detection(self):
        with mock.patch("jevperf.compatibility.detect_hermes_version", return_value=None):
            result = detect_compatibility(FakeContext())
        self.assertEqual(result["level"], "supported")
        self.assertIsNone(result["version_meets_floor"])

    def test_missing_optional_cli_surface_is_still_supported_for_runtime(self):
        with mock.patch("jevperf.compatibility.detect_hermes_version", return_value="0.21.5"):
            result = detect_compatibility(FakeContext(cli=False))
        self.assertEqual(result["level"], "supported")
        self.assertFalse(result["cli_controls_ready"])

    def test_missing_routing_surface_is_degraded(self):
        with mock.patch("jevperf.compatibility.detect_hermes_version", return_value="0.21.5"):
            result = detect_compatibility(FakeContext(middleware=False))
        self.assertEqual(result["level"], "degraded")
        self.assertFalse(result["routing_surface_ready"])

    def test_missing_base_surface_is_unsupported(self):
        class Broken:
            pass
        with mock.patch("jevperf.compatibility.detect_hermes_version", return_value="0.21.5"):
            result = detect_compatibility(Broken())
        self.assertEqual(result["level"], "unsupported")
        self.assertFalse(result["phase1_supported"])


if __name__ == "__main__":
    unittest.main()
