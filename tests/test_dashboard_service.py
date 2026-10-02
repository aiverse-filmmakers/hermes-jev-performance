import tempfile
import time
import unittest
from pathlib import Path

from jevperf.dashboard_service import (
    PLUGIN_ID,
    read_dashboard_config,
    set_dashboard_mode,
    status_payload,
    summary_payload,
)
from jevperf.routing import RoutingDecision
from jevperf.store import MetricsStore


class SettingsHarness:
    def __init__(self, **values):
        self.values = {
            "mode": "shadow",
            "provider": "openrouter",
            "model": "typesafe/jev-1.13",
            "min_confidence": 0.70,
            "timeout_seconds": 2.5,
            "notice": False,
            "retention_days": 30,
            "telemetry_enabled": True,
            **values,
        }

    def loader(self, plugin_id, plugin_root):
        self.last_plugin_id = plugin_id
        self.last_plugin_root = plugin_root
        return [
            {"key": key, "value": value}
            for key, value in self.values.items()
        ]

    def writer(self, plugin_id, plugin_root, values):
        self.last_write = (plugin_id, plugin_root, dict(values))
        self.values.update(values)


class DashboardServiceTests(unittest.TestCase):
    def make_store(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return MetricsStore(Path(temp.name) / "metrics.sqlite3")

    def test_reads_config_through_plugin_settings_surface(self):
        settings = SettingsHarness(mode="on", notice=True)
        config = read_dashboard_config(settings.loader)
        self.assertEqual(config.mode, "on")
        self.assertTrue(config.notice)
        self.assertEqual(settings.last_plugin_id, PLUGIN_ID)

    def test_status_contains_safe_runtime_fields_and_24h_summary(self):
        settings = SettingsHarness(mode="shadow")
        store = self.make_store()
        now = time.time()
        store.touch_turn("opaque", "shadow", now=now)
        store.record_decision(
            turn_key="opaque",
            mode="shadow",
            decision=RoutingDecision(
                family="web",
                confidence=0.9,
                accepted=True,
                reason="accepted",
                latency_ms=250,
                cost_usd=0.00002,
            ),
            applied=False,
            reason="shadow",
            now=now + 0.1,
        )
        payload = status_payload(field_loader=settings.loader, store=store)
        self.assertEqual(payload["mode"], "shadow")
        self.assertEqual(payload["telemetry"]["database_state"], "ready")
        self.assertEqual(payload["summary_24h"]["decisions"], 1)
        serialized = repr(payload)
        self.assertNotIn(str(store.path), serialized)
        self.assertNotIn("plugin-data", serialized)

    def test_summary_is_aggregate_only(self):
        store = self.make_store()
        now = time.time()
        store.touch_turn("opaque", "on", now=now)
        store.record_decision(
            turn_key="opaque",
            mode="on",
            decision=RoutingDecision(
                family="terminal",
                confidence=0.95,
                accepted=True,
                reason="accepted",
                latency_ms=123,
                cost_usd=0.00001,
            ),
            applied=True,
            reason="filtered",
            now=now + 0.1,
        )
        payload = summary_payload(hours=24, store=store)
        self.assertEqual(payload["routes"], [{"family": "terminal", "count": 1}])
        self.assertNotIn("turn_key", payload)
        self.assertNotIn("path", payload)

    def test_mode_write_uses_canonical_writer_and_verifies_readback(self):
        settings = SettingsHarness(mode="shadow")
        store = self.make_store()
        result = set_dashboard_mode(
            "on",
            settings_writer=settings.writer,
            field_loader=settings.loader,
            store=store,
        )
        self.assertEqual(result, {
            "ok": True,
            "previous_mode": "shadow",
            "mode": "on",
        })
        self.assertEqual(settings.last_write[0], PLUGIN_ID)
        self.assertEqual(settings.last_write[2], {"mode": "on"})

    def test_mode_write_rejects_invalid_values(self):
        settings = SettingsHarness()
        with self.assertRaises(ValueError):
            set_dashboard_mode(
                "turbo",
                settings_writer=settings.writer,
                field_loader=settings.loader,
            )

    def test_mode_write_requires_readback_match(self):
        settings = SettingsHarness(mode="shadow")

        def no_op_writer(plugin_id, plugin_root, values):
            pass

        with self.assertRaises(RuntimeError):
            set_dashboard_mode(
                "on",
                settings_writer=no_op_writer,
                field_loader=settings.loader,
            )


if __name__ == "__main__":
    unittest.main()
