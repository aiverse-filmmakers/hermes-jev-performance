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
        self.assertEqual(stats.p50_jev_latency_ms, 400)
        self.assertEqual(stats.p95_jev_latency_ms, 400)
        self.assertAlmostEqual(stats.avg_jev_cost_usd, 0.00001)
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

    def test_latency_percentiles_are_interpolated(self):
        store, _ = self.make_store()
        for index, latency in enumerate((100, 200, 300, 400, 500)):
            key = f"turn-{index}"
            store.touch_turn(key, "shadow", now=1000 + index)
            store.record_decision(
                turn_key=key,
                mode="shadow",
                decision=RoutingDecision(
                    family="web",
                    confidence=0.9,
                    accepted=True,
                    reason="accepted",
                    latency_ms=latency,
                    cost_usd=0.00001 * (index + 1),
                ),
                applied=False,
                reason="shadow",
                now=1000 + index + 0.1,
            )
        stats = store.summary(since_hours=1, now=1010)
        self.assertEqual(stats.p50_jev_latency_ms, 300)
        self.assertEqual(stats.p95_jev_latency_ms, 480)
        self.assertAlmostEqual(stats.avg_jev_cost_usd, 0.00003)
        self.assertAlmostEqual(stats.total_jev_cost_usd, 0.00015)

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

    def test_v1_database_migrates_through_v3(self):
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
        self.assertEqual(version, "3")

    def test_v2_database_migrates_to_v3(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "metrics.sqlite3"

        with sqlite3.connect(path) as con:
            con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            con.execute(
                "INSERT INTO meta(key, value) VALUES('schema_version', '2')"
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
                    status TEXT NOT NULL DEFAULT 'running',
                    route_reason TEXT
                )
                """
            )

        store = MetricsStore(path)
        store.initialize()

        with sqlite3.connect(path) as con:
            columns = {
                row[1] for row in con.execute("PRAGMA table_info(hermes_turns)")
            }
            tables = {
                row[0]
                for row in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            version = con.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()[0]

        self.assertEqual(version, "3")
        self.assertIn("benchmark_run_id", columns)
        self.assertIn("benchmark_sample_id", columns)
        self.assertIn("benchmark_fixture_id", columns)
        self.assertIn("benchmark_warmup", columns)
        self.assertIn("benchmark_runs", tables)
        self.assertIn("benchmark_samples", tables)

    def test_schema_v3_initialize_is_idempotent(self):
        store, path = self.make_store()
        store.initialize()
        store._initialized = False
        store.initialize()
        with sqlite3.connect(path) as con:
            version = con.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()[0]
            indexes = {
                row[1]
                for row in con.execute("PRAGMA index_list(hermes_turns)")
            }
        self.assertEqual(version, "3")
        self.assertIn("idx_hermes_turns_benchmark_run", indexes)

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
    def test_off_shadow_on_records_are_queryable(self):
        store, path = self.make_store()

        store.touch_turn("off-turn", "off", now=100)
        store.record_turn_reason("off-turn", "mode_off")
        store.finish_turn("off-turn", status="complete", now=101)

        shadow = RoutingDecision(
            family="web",
            confidence=0.9,
            accepted=True,
            reason="accepted",
        )
        store.touch_turn("shadow-turn", "shadow", now=110)
        store.record_decision(
            turn_key="shadow-turn",
            mode="shadow",
            decision=shadow,
            applied=False,
            reason="shadow",
            now=110.1,
        )
        store.finish_turn("shadow-turn", status="complete", now=111)

        on = RoutingDecision(
            family="terminal",
            confidence=0.95,
            accepted=True,
            reason="accepted",
        )
        store.touch_turn("on-turn", "on", now=120)
        store.record_decision(
            turn_key="on-turn",
            mode="on",
            decision=on,
            applied=True,
            reason="filtered",
            now=120.1,
        )
        store.finish_turn("on-turn", status="complete", now=121)

        with sqlite3.connect(path) as con:
            rows = con.execute(
                """
                SELECT mode, route_family, route_applied, route_reason
                FROM hermes_turns
                ORDER BY started_at
                """
            ).fetchall()

        self.assertEqual(
            rows,
            [
                ("off", None, 0, "mode_off"),
                ("shadow", "web", 0, "shadow"),
                ("on", "terminal", 1, "filtered"),
            ],
        )

if __name__ == "__main__":
    unittest.main()
