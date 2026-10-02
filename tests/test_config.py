import os
import unittest
from unittest import mock

from jevperf.benchmark_context import (
    FIXTURE_ID_ENV,
    MODE_ENV,
    RUN_ID_ENV,
    SAMPLE_ID_ENV,
)
from jevperf.config import (
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_MODE,
    DEFAULT_NOTICE,
    DEFAULT_RETENTION_DAYS,
    DEFAULT_TELEMETRY_ENABLED,
    DEFAULT_TIMEOUT_SECONDS,
    read_config,
)
from tests.fakes import FakeContext


class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        config = read_config(FakeContext())
        self.assertEqual(config.mode, DEFAULT_MODE)
        self.assertEqual(config.min_confidence, DEFAULT_MIN_CONFIDENCE)
        self.assertEqual(config.timeout_seconds, DEFAULT_TIMEOUT_SECONDS)
        self.assertEqual(config.notice, DEFAULT_NOTICE)
        self.assertEqual(config.retention_days, DEFAULT_RETENTION_DAYS)
        self.assertEqual(config.telemetry_enabled, DEFAULT_TELEMETRY_ENABLED)
        self.assertEqual(config.warnings, ())

    def test_normalizes_valid_values(self):
        config = read_config(FakeContext({
            "mode": " ON ",
            "provider": " OpenRouter ",
            "model": "typesafe/jev-test",
            "min_confidence": 0.82,
            "timeout_seconds": 4,
            "notice": True,
            "retention_days": 90,
            "telemetry_enabled": False,
        }))
        self.assertEqual(config.mode, "on")
        self.assertEqual(config.provider, "openrouter")
        self.assertEqual(config.model, "typesafe/jev-test")
        self.assertEqual(config.min_confidence, 0.82)
        self.assertEqual(config.timeout_seconds, 4.0)
        self.assertTrue(config.notice)
        self.assertEqual(config.retention_days, 90)
        self.assertFalse(config.telemetry_enabled)

    def test_invalid_values_fall_back(self):
        config = read_config(FakeContext({
            "mode": "turbo",
            "min_confidence": 2,
            "timeout_seconds": 0,
            "notice": "yes",
            "retention_days": -5,
            "telemetry_enabled": "yes",
        }))
        self.assertEqual(config.mode, DEFAULT_MODE)
        self.assertEqual(config.min_confidence, DEFAULT_MIN_CONFIDENCE)
        self.assertEqual(config.timeout_seconds, DEFAULT_TIMEOUT_SECONDS)
        self.assertEqual(config.notice, DEFAULT_NOTICE)
        self.assertEqual(config.retention_days, DEFAULT_RETENTION_DAYS)
        self.assertEqual(config.telemetry_enabled, DEFAULT_TELEMETRY_ENABLED)
        self.assertGreaterEqual(len(config.warnings), 6)

    def test_benchmark_mode_override_is_process_scoped(self):
        env = {
            RUN_ID_ENV: "bench-a",
            SAMPLE_ID_ENV: "sample-a",
            FIXTURE_ID_ENV: "files-test",
            MODE_ENV: "off",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            config = read_config(FakeContext({"mode": "shadow"}))
        self.assertEqual(config.mode, "off")
        self.assertEqual(FakeContext({"mode": "shadow"}).settings["mode"], "shadow")

    def test_mode_env_without_benchmark_context_is_ignored(self):
        with mock.patch.dict(os.environ, {MODE_ENV: "off"}, clear=True):
            config = read_config(FakeContext({"mode": "shadow"}))
        self.assertEqual(config.mode, "shadow")

if __name__ == "__main__":
    unittest.main()
