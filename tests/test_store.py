import sqlite3
import tempfile
import unittest
from pathlib import Path

from jevperf.routing import RoutingDecision
from jevperf.store import MetricsStore, StoreSchemaError


class StoreTests(unittest.TestCase):
    def make_store(self):
        temp = tempfile.TemporaryDirectory()
        path = Path(temp.name) / "metrics.sqlite3"
        store = MetricsStore(path)
        self.addCleanup(temp.cleanup)
        return store, path

    def test_schema_and_summary(self):
        store, path = self.make_store()
        decision = RoutingDecision(
            family="web",
            confidence=0.9,
            accepted=True,
            reason="accepted",
            provider="openrouter",
            requested_model="typesafe/jev-1.13",
            actual_model="typesafe/jev-1.13-20260917",
            latency_ms=400,
            cost_usd=0.00001,
            input_tokens=100,
            output_tokens=10,
        )

        store.touch_turn("opaque-turn", "on", now=1000)
        store.record_decision(
            turn_key="opaque-turn",
            mode="on",
            decision=decision,
            applied=True,
            reason="filtered",
            now=1000.1,
        )
        store.increment_llm_request("opaque-turn")
        store.increment_llm_request("opaque-turn")
        store.increment_tool_call("opaque-turn")
        store.add_usage(
            "opaque-turn",
            {
                "input_tokens": 1200,
                "output_tokens": 150,
                "input_tokens_details": {"cached_tokens": 300},
                "output_tokens_details": {"reasoning_tokens": 25},
            },
        )
        store.record_turn_reason("opaque-turn", "filtered")
        store.finish_turn("opaque-turn", status="complete", now=1002)

        stats = store.summary(since_hours=1, now=1003)
        self.assertEqual(stats.decisions, 1)
        self.assertEqual(stats.turns, 1)
        self.assertEqual(stats.applied, 1)
        self.assertEqual(stats.fallback, 0)
        self.assertEqual(stats.avg_confidence, 0.9)
        self.assertEqual(stats.avg_jev_latency_ms, 400)
        self.assertAlmostEqual(stats.total_jev_cost_usd, 0.00001)
        self.assertEqual(stats.avg_turn_duration_ms, 2000)
        self.assertEqual(stats.avg_tool_calls, 1)
        self.assertEqual(stats.avg_llm_requests, 2)
        self.assertEqual(stats.input_tokens, 1200)
        self.assertEqual(stats.output_tokens, 150)
        self.assertEqual(stats.routes, (("web", 1),))

        with sqlite3.connect(path) as con:
            turn = con.execute(
                """
                SELECT cached_input_tokens, reasoning_tokens, status, route_reason
                FROM hermes_turns WHERE turn_key = ?
                """,
                ("opaque-turn",),
            ).fetchone()
        self.assertEqual(turn, (300, 25, "complete", "filtered"))

    def test_decision_is_unique_per_turn(self):
        store, _ = self.make_store()
        store.touch_turn("opaque", "shadow", now=10)
        first = RoutingDecision("web", 0.9, True, "accepted")
        second = RoutingDecision("terminal", 0.99, True, "accepted")

        store.record_decision(
            turn_key="opaque",
            mode="shadow",
            decision=first,
            applied=False,
            reason="shadow",
            now=11,
        )
        store.record_decision(
            turn_key="opaque",
            mode="shadow",
            decision=second,
            applied=False,
            reason="shadow",
            now=12,
        )

        stats = store.summary(since_hours=1, now=20)
        self.assertEqual(stats.decisions, 1)
        self.assertEqual(stats.routes, (("web", 1),))

    def test_mode_change_is_metadata_only(self):
        store, path = self.make_store()
        store.record_mode_change("shadow", "on", source="slash", now=10)
        with sqlite3.connect(path) as con:
            row = con.execute(
                "SELECT old_mode, new_mode, source FROM mode_changes"
            ).fetchone()
        self.assertEqual(row, ("shadow", "on", "slash"))

    def test_retention_cleanup(self):
        store, _ = self.make_store()
        store.touch_turn("old", "off", now=0)
        store.touch_turn("new", "off", now=200000)
        store.cleanup(1, now=200001)

        stats = store.summary(since_hours=1000, now=200001)
        self.assertEqual(stats.turns, 1)

    def test_schema_has_no_content_columns(self):
        store, path = self.make_store()
        store.initialize()
        forbidden = {
            "prompt",
            "state",
            "user_message",
            "tool_args",
            "tool_result",
            "response",
            "conversation_history",
        }
        with sqlite3.connect(path) as con:
            for table in ("jev_decisions", "hermes_turns", "mode_changes"):
                columns = {
                    row[1] for row in con.execute(f"PRAGMA table_info({table})")
                }
                self.assertTrue(forbidden.isdisjoint(columns))

    def test_v1_database_migrates_to_v2(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "metrics.sqlite3"

        with sqlite3.connect(path) as con:
            con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            con.execute(
                "INSERT INTO meta(key, value) VALUES('schema_version', '1')"
            )
            con.execute(
                """
                CREATE TABLE hermes_turns (
                    turn_key TEXT PRIMARY KEY,
                    started_at REAL NOT NULL,
                    completed_at REAL,
                    mode TEXT NOT NULL,
                    route_family TEXT,
                    route_applied INTEGER NOT NULL DEFAULT 0,
                    duration_ms REAL,
                    llm_requests INTEGER NOT NULL DEFAULT 0,
                    tool_calls INTEGER NOT NULL DEFAULT 0,
                    input_tokens INTEGER,
                    cached_input_tokens INTEGER,
                    output_tokens INTEGER,
                    reasoning_tokens INTEGER,
                    status TEXT NOT NULL DEFAULT 'running'
                )
                """
            )

        store = MetricsStore(path)
        store.initialize()

        with sqlite3.connect(path) as con:
            columns = {
                row[1] for row in con.execute("PRAGMA table_info(hermes_turns)")
            }
            version = con.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()[0]

        self.assertIn("route_reason", columns)
        self.assertEqual(version, "2")

    def test_newer_schema_fails_closed_for_store_only(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "metrics.sqlite3"

        with sqlite3.connect(path) as con:
            con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            con.execute(
                "INSERT INTO meta(key, value) VALUES('schema_version', '999')"
            )

        with self.assertRaises(StoreSchemaError):
            MetricsStore(path).initialize()

if __name__ == "__main__":
    unittest.main()
