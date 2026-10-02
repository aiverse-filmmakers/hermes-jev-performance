import tempfile
import time
import unittest
from pathlib import Path

from jevperf.dashboard_service import analytics_payload
from jevperf.routing import RoutingDecision
from jevperf.store import MetricsStore


class DashboardAnalyticsTests(unittest.TestCase):
    def make_store(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return MetricsStore(Path(temp.name) / "metrics.sqlite3")

    def populate_modes(self, store):
        now = time.time()

        store.touch_turn("off", "off", now=now - 30)
        store.increment_llm_request("off")
        store.increment_tool_call("off")
        store.add_usage("off", {"input_tokens": 1000, "output_tokens": 100})
        store.record_turn_reason("off", "mode_off")
        store.finish_turn("off", status="complete", now=now - 29)

        store.touch_turn("shadow", "shadow", now=now - 20)
        store.increment_llm_request("shadow")
        store.increment_llm_request("shadow")
        store.increment_tool_call("shadow")
        store.increment_tool_call("shadow")
        store.add_usage("shadow", {"input_tokens": 1500, "output_tokens": 160})
        store.record_decision(
            turn_key="shadow",
            mode="shadow",
            decision=RoutingDecision(
                family="web",
                confidence=0.88,
                accepted=True,
                reason="accepted",
                latency_ms=300,
                cost_usd=0.00002,
            ),
            applied=False,
            reason="shadow",
            now=now - 19.9,
        )
        store.finish_turn("shadow", status="complete", now=now - 18)

        store.touch_turn("on", "on", now=now - 10)
        store.increment_llm_request("on")
        store.increment_tool_call("on")
        store.add_usage(
            "on",
            {
                "input_tokens": 800,
                "output_tokens": 90,
                "input_tokens_details": {"cached_tokens": 200},
                "output_tokens_details": {"reasoning_tokens": 20},
            },
        )
        store.record_decision(
            turn_key="on",
            mode="on",
            decision=RoutingDecision(
                family="terminal",
                confidence=0.96,
                accepted=True,
                reason="accepted",
                latency_ms=180,
                cost_usd=0.00001,
            ),
            applied=True,
            reason="filtered",
            now=now - 9.9,
        )
        store.finish_turn("on", status="complete", now=now - 9)

    def test_mode_comparison_covers_all_modes(self):
        store = self.make_store()
        self.populate_modes(store)
        rows = store.mode_comparison(since_hours=24)
        self.assertEqual([row["mode"] for row in rows], ["off", "shadow", "on"])
        by_mode = {row["mode"]: row for row in rows}
        self.assertEqual(by_mode["off"]["turns"], 1)
        self.assertEqual(by_mode["off"]["decisions"], 0)
        self.assertEqual(by_mode["shadow"]["decisions"], 1)
        self.assertEqual(by_mode["shadow"]["applied"], 0)
        self.assertEqual(by_mode["on"]["applied"], 1)
        self.assertEqual(by_mode["on"]["avg_input_tokens"], 800)

    def test_recent_decisions_never_expose_turn_key(self):
        store = self.make_store()
        self.populate_modes(store)
        rows = store.recent_decisions(since_hours=24, limit=10)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all("turn_key" not in row for row in rows))
        self.assertEqual(rows[0]["family"], "terminal")

    def test_reason_breakdown_includes_off_shadow_and_filtered(self):
        store = self.make_store()
        self.populate_modes(store)
        reasons = {
            row["reason"]: row["count"]
            for row in store.reason_breakdown(since_hours=24)
        }
        self.assertEqual(reasons["mode_off"], 1)
        self.assertEqual(reasons["shadow"], 1)
        self.assertEqual(reasons["filtered"], 1)

    def test_time_series_is_bounded_aggregate_data(self):
        store = self.make_store()
        self.populate_modes(store)
        series = store.time_series(since_hours=24, points=24)
        self.assertGreaterEqual(len(series), 1)
        self.assertLessEqual(len(series), 24)
        for row in series:
            self.assertNotIn("turn_key", row)
            self.assertIn("avg_duration_ms", row)
            self.assertIn("input_tokens", row)

    def test_analytics_payload_is_dashboard_safe(self):
        store = self.make_store()
        self.populate_modes(store)
        payload = analytics_payload(hours=24, limit=10, store=store)
        self.assertEqual(payload["database_state"], "ready")
        self.assertEqual(
            {row["family"] for row in payload["routes"]},
            {"web", "terminal"},
        )
        serialized = repr(payload)
        self.assertNotIn(str(store.path), serialized)
        self.assertNotIn("turn_key", serialized)


if __name__ == "__main__":
    unittest.main()
