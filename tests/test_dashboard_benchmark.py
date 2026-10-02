import tempfile
import time
import unittest
from pathlib import Path

from jevperf.benchmark import BENCHMARK_VERSION
from jevperf.benchmark_context import BenchmarkContext
from jevperf.dashboard_service import (
    benchmark_export_payload,
    benchmark_runs_payload,
)
from jevperf.routing import RoutingDecision
from jevperf.store import MetricsStore


class DashboardBenchmarkTests(unittest.TestCase):
    def make_store(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return MetricsStore(Path(temp.name) / "metrics.sqlite3")

    def seed(self, store):
        now = time.time()
        store.start_benchmark_run(
            run_id="bench-dashboard",
            benchmark_version=BENCHMARK_VERSION,
            fixture_set_hash="b" * 64,
            fixture_count=1,
            repeats=2,
            warmups=0,
            environment={
                "plugin_version": "0.1.0-test",
                "hermes_version": "0.21.5",
                "python_version": "3.14.7",
                "os_family": "Linux",
                "architecture": "x86_64",
                "provider": "openrouter",
                "jev_model": "typesafe/jev-1.13",
                "fixture_set_sha256": "b" * 64,
                "repeats": 2,
                "warmups": 0,
                "order_policy": "paired_alternating",
                "python_implementation": "CPython",
                "hostname": "DO_NOT_RETURN",
            },
            methodology={
                "kind": "controlled_matched_benchmark",
                "order_policy": "paired_alternating",
                "private_note": "DO_NOT_RETURN_METHODOLOGY",
            },
            now=now,
        )

        for index, mode in enumerate(("off", "on", "on", "off")):
            repeat_index = 0 if index < 2 else 1
            sample_id = f"private-sample-{index}"
            store.plan_benchmark_sample(
                sample_id=sample_id,
                run_id="bench-dashboard",
                fixture_id="files-test",
                family="files",
                mode=mode,
                repeat_index=repeat_index,
                order_index=index,
                is_warmup=False,
                now=now + index,
            )
            context = BenchmarkContext(
                run_id="bench-dashboard",
                sample_id=sample_id,
                fixture_id="files-test",
                is_warmup=False,
            )
            turn_key = f"private-turn-{index}"
            store.touch_turn(
                turn_key,
                mode,
                benchmark=context,
                now=now + index,
            )
            store.increment_llm_request(turn_key)
            store.increment_tool_call(turn_key)
            store.record_runtime_identity(
                turn_key,
                provider="/Users/private/provider",
                requested_model="/Users/private/model",
                response_model="private-org/model-v1",
                api_mode="private-api-mode",
            )
            store.add_usage(
                turn_key,
                {
                    "input_tokens": 1000 if mode == "off" else 800,
                    "output_tokens": 100 if mode == "off" else 90,
                },
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
                        latency_ms=150,
                        cost_usd=0.00001,
                    ),
                    applied=True,
                    reason="filtered",
                    now=now + index + 0.1,
                )
            else:
                store.record_turn_reason(turn_key, "mode_off")
            store.finish_turn(
                turn_key,
                status="complete",
                now=now + index + (1.0 if mode == "off" else 0.8),
            )
            store.finalize_benchmark_sample(
                sample_id,
                runner_duration_ms=1100 if mode == "off" else 900,
                exit_code=0,
                validation_passed=True,
                now=now + index + 2,
            )

        store.finish_benchmark_run(
            "bench-dashboard",
            status="complete",
            now=now + 10,
        )

    def test_dashboard_list_contains_comparison_not_private_runtime_identity(self):
        store = self.make_store()
        self.seed(store)
        payload = benchmark_runs_payload(limit=10, store=store)
        self.assertEqual(payload["database_state"], "ready")
        self.assertEqual(len(payload["runs"]), 1)
        run = payload["runs"][0]
        self.assertEqual(run["comparison"]["matched_pairs"], 2)
        self.assertEqual(run["failed_samples"], 0)
        self.assertNotIn("hermes_providers", run)
        self.assertNotIn("hermes_models", run)
        self.assertNotIn("hermes_api_modes", run)
        serialized = repr(payload)
        self.assertNotIn("private-sample", serialized)
        self.assertNotIn("private-turn", serialized)
        self.assertNotIn("DO_NOT_RETURN", serialized)
        self.assertNotIn("DO_NOT_RETURN_METHODOLOGY", serialized)
        self.assertNotIn("/Users/private", serialized)
        self.assertNotIn("private-org", serialized)
        self.assertNotIn("private-api-mode", serialized)

    def test_dashboard_counts_routing_invalid_on_sample_as_failed(self):
        store = self.make_store()
        self.seed(store)
        with store._connection() as con:
            con.execute(
                """
                UPDATE benchmark_samples
                SET route_family = 'web', route_applied = 0
                WHERE mode = 'on' AND repeat_index = 0
                """
            )
        payload = benchmark_runs_payload(limit=10, store=store)
        run = payload["runs"][0]
        self.assertEqual(run["comparison"]["matched_pairs"], 1)
        self.assertEqual(run["comparison"]["invalid_routing_samples"]["on"], 1)
        self.assertEqual(run["failed_samples"], 1)

    def test_dashboard_export_is_anonymized(self):
        store = self.make_store()
        self.seed(store)
        payload = benchmark_export_payload("bench-dashboard", store=store)
        serialized = repr(payload)
        self.assertNotIn("private-sample", serialized)
        self.assertNotIn("private-turn", serialized)
        self.assertNotIn("DO_NOT_RETURN", serialized)
        self.assertNotIn("/Users/private", serialized)
        self.assertNotIn("private-org", serialized)
        self.assertEqual(
            payload["comparison"]["interpretation"],
            "controlled_matched_benchmark",
        )


if __name__ == "__main__":
    unittest.main()
