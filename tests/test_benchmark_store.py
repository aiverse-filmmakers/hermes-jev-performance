import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from jevperf.benchmark import BENCHMARK_VERSION, calculate_comparison
from jevperf.benchmark_context import BenchmarkContext
from jevperf.benchmark_export import build_anonymized_export
from jevperf.routing import RoutingDecision
from jevperf.store import MetricsStore


class BenchmarkStoreTests(unittest.TestCase):
    def make_store(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "metrics.sqlite3"
        return MetricsStore(path), path

    def seed_run(self, store):
        now = time.time()
        store.start_benchmark_run(
            run_id="bench-test",
            benchmark_version=BENCHMARK_VERSION,
            fixture_set_hash="a" * 64,
            fixture_count=1,
            repeats=2,
            warmups=0,
            environment={
                "plugin_version": "test",
                "hermes_version": "0.21.5",
                "python_version": "3.14.7",
                "os_family": "Linux",
                "architecture": "x86_64",
                "provider": "openrouter",
                "jev_model": "typesafe/jev-1.13",
                "fixture_set_sha256": "a" * 64,
                "repeats": 2,
                "warmups": 0,
                "order_policy": "paired_alternating",
                "python_implementation": "CPython",
                "hostname": "MUST_NOT_EXPORT",
            },
            methodology={
                "kind": "controlled_matched_benchmark",
                "warmups_excluded_from_deltas": True,
                "order_policy": "paired_alternating",
                "private_note": "MUST_NOT_EXPORT_METHODOLOGY",
            },
            now=now,
        )
        return now

    def add_sample(
        self,
        store,
        *,
        sample_id,
        mode,
        repeat_index,
        order_index,
        duration,
        tools,
        llm,
        input_tokens,
        output_tokens,
        now,
    ):
        store.plan_benchmark_sample(
            sample_id=sample_id,
            run_id="bench-test",
            fixture_id="files-read-readme-heading",
            family="files",
            mode=mode,
            repeat_index=repeat_index,
            order_index=order_index,
            is_warmup=False,
            now=now,
        )
        context = BenchmarkContext(
            run_id="bench-test",
            sample_id=sample_id,
            fixture_id="files-read-readme-heading",
            is_warmup=False,
        )
        turn_key = "turn-" + sample_id
        store.touch_turn(turn_key, mode, benchmark=context, now=now)
        for _ in range(llm):
            store.increment_llm_request(turn_key)
        for _ in range(tools):
            store.increment_tool_call(turn_key)
        store.add_usage(
            turn_key,
            {"input_tokens": input_tokens, "output_tokens": output_tokens},
        )
        store.record_runtime_identity(
            turn_key,
            provider="synthetic-provider",
            requested_model="synthetic-model",
            response_model="synthetic-model-v1",
            api_mode="synthetic-api",
        )
        if mode == "on":
            store.record_decision(
                turn_key=turn_key,
                mode="on",
                decision=RoutingDecision(
                    family="files",
                    confidence=0.95,
                    accepted=True,
                    reason="accepted",
                    latency_ms=200,
                    cost_usd=0.00001,
                ),
                applied=True,
                reason="filtered",
                now=now + 0.01,
            )
        else:
            store.record_turn_reason(turn_key, "mode_off")
        store.finish_turn(
            turn_key,
            status="complete",
            now=now + (duration / 1000.0),
        )
        return store.finalize_benchmark_sample(
            sample_id,
            runner_duration_ms=duration + 50,
            exit_code=0,
            validation_passed=True,
            now=now + (duration / 1000.0) + 0.01,
        )

    def test_benchmark_rows_are_excluded_from_observational_summary(self):
        store, _ = self.make_store()
        now = self.seed_run(store)

        self.add_sample(
            store,
            sample_id="sample-off",
            mode="off",
            repeat_index=0,
            order_index=0,
            duration=1000,
            tools=3,
            llm=2,
            input_tokens=1000,
            output_tokens=100,
            now=now,
        )
        self.add_sample(
            store,
            sample_id="sample-on",
            mode="on",
            repeat_index=0,
            order_index=1,
            duration=800,
            tools=2,
            llm=1,
            input_tokens=800,
            output_tokens=90,
            now=now + 2,
        )

        organic = store.summary(since_hours=24)
        self.assertEqual(organic.turns, 0)
        self.assertEqual(organic.decisions, 0)
        self.assertEqual(store.recent_decisions(since_hours=24), [])
        self.assertEqual(
            [row["turns"] for row in store.mode_comparison(since_hours=24)],
            [0, 0, 0],
        )

    def test_benchmark_samples_capture_hermes_and_jev_metrics(self):
        store, _ = self.make_store()
        now = self.seed_run(store)
        row = self.add_sample(
            store,
            sample_id="sample-on",
            mode="on",
            repeat_index=0,
            order_index=0,
            duration=800,
            tools=2,
            llm=1,
            input_tokens=800,
            output_tokens=90,
            now=now,
        )

        self.assertEqual(row["status"], "complete")
        self.assertAlmostEqual(row["hermes_duration_ms"], 800, places=2)
        self.assertEqual(row["tool_calls"], 2)
        self.assertEqual(row["llm_requests"], 1)
        self.assertEqual(row["hermes_provider"], "synthetic-provider")
        self.assertEqual(row["hermes_requested_model"], "synthetic-model")
        self.assertEqual(row["hermes_response_model"], "synthetic-model-v1")
        self.assertEqual(row["hermes_api_mode"], "synthetic-api")
        self.assertEqual(row["route_family"], "files")
        self.assertTrue(row["route_applied"])
        self.assertEqual(row["jev_latency_ms"], 200)
        self.assertAlmostEqual(row["jev_cost_usd"], 0.00001)

    def test_benchmark_comparison_uses_measured_pairs(self):
        store, _ = self.make_store()
        now = self.seed_run(store)
        pairs = [
            ("off-0", "off", 0, 0, 1000, 3, 2, 1000, 100),
            ("on-0", "on", 0, 1, 800, 2, 1, 800, 90),
            ("on-1", "on", 1, 2, 900, 2, 1, 850, 90),
            ("off-1", "off", 1, 3, 1200, 4, 2, 1100, 100),
        ]
        for offset, row in enumerate(pairs):
            self.add_sample(
                store,
                sample_id=row[0],
                mode=row[1],
                repeat_index=row[2],
                order_index=row[3],
                duration=row[4],
                tools=row[5],
                llm=row[6],
                input_tokens=row[7],
                output_tokens=row[8],
                now=now + (offset * 3),
            )

        samples = store.benchmark_samples("bench-test", include_warmups=True)
        result = calculate_comparison(samples)
        self.assertEqual(result["matched_pairs"], 2)
        self.assertEqual(
            result["metrics"]["hermes_duration_ms"]["absolute_delta"],
            -250,
        )

    def test_anonymized_export_strips_ids_paths_runtime_identity_and_unknown_metadata(self):
        store, path = self.make_store()
        now = self.seed_run(store)
        self.add_sample(
            store,
            sample_id="private-sample-id",
            mode="off",
            repeat_index=0,
            order_index=0,
            duration=1000,
            tools=3,
            llm=2,
            input_tokens=1000,
            output_tokens=100,
            now=now,
        )
        store.finish_benchmark_run("bench-test", status="complete", now=now + 2)

        payload = build_anonymized_export(store, "bench-test")
        serialized = repr(payload)
        self.assertNotIn("private-sample-id", serialized)
        self.assertNotIn("MUST_NOT_EXPORT", serialized)
        self.assertNotIn("MUST_NOT_EXPORT_METHODOLOGY", serialized)
        self.assertNotIn(str(path), serialized)
        self.assertNotIn("turn_key", serialized)
        self.assertNotIn("synthetic-provider", serialized)
        self.assertNotIn("synthetic-model", serialized)
        self.assertNotIn("synthetic-model-v1", serialized)
        self.assertNotIn("synthetic-api", serialized)
        self.assertFalse(payload["privacy"]["prompt_text_included"])
        self.assertFalse(payload["privacy"]["host_identifiers_included"])
        self.assertFalse(payload["privacy"]["primary_runtime_identity_included"])

    def test_schema_v4_has_benchmark_tables_without_content_columns(self):
        store, path = self.make_store()
        store.initialize()
        forbidden = {
            "prompt",
            "user_message",
            "conversation_history",
            "tool_args",
            "tool_result",
            "response",
            "hostname",
            "username",
            "cwd",
        }
        with sqlite3.connect(path) as con:
            tables = {
                row[0]
                for row in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            self.assertIn("benchmark_runs", tables)
            self.assertIn("benchmark_samples", tables)
            for table in ("benchmark_runs", "benchmark_samples"):
                columns = {
                    row[1]
                    for row in con.execute(f"PRAGMA table_info({table})")
                }
                self.assertTrue(forbidden.isdisjoint(columns))


if __name__ == "__main__":
    unittest.main()
