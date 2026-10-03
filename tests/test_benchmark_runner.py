import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from jevperf.benchmark_context import read_benchmark_context, read_benchmark_mode
from jevperf.benchmark_runner import run_live_benchmark
from jevperf.credentials import Credential
from jevperf.routing import RoutingDecision
from jevperf.store import StoreProvider
from tests.fakes import FakeContext


class FakeTelemetry:
    def __init__(self, path):
        self.stores = StoreProvider(lambda: path)
        self.mode_changes = []

    def record_mode_change(self, old_mode, new_mode, *, source):
        self.mode_changes.append((old_mode, new_mode, source))


class BenchmarkRunnerTests(unittest.TestCase):
    def make_fixture_file(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "suite.json"
        path.write_text(
            """
            {
              "suite_version": 1,
              "fixtures": [
                {
                  "id": "files-test",
                  "family": "files",
                  "prompt": "Read README.md only.",
                  "read_only": true,
                  "requires_network": false
                }
              ]
            }
            """,
            encoding="utf-8",
        )
        return path

    def make_runtime(self, **settings):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        db = Path(temp.name) / "metrics.sqlite3"
        ctx = FakeContext({
            "mode": "shadow",
            "provider": "openrouter",
            "model": "typesafe/jev-1.13",
            "telemetry_enabled": True,
            **settings,
        })
        telemetry = FakeTelemetry(db)
        return ctx, telemetry

    def credential_patch(self):
        return mock.patch(
            "jevperf.benchmark_runner.resolve_openrouter_credential",
            return_value=Credential(name="OPENROUTER_JEV_API_TOKEN", token="fixture-token"),
        )

    def test_live_runner_pairs_modes_collects_metrics_and_restores_mode(self):
        ctx, telemetry = self.make_runtime()
        fixture_path = self.make_fixture_file()
        store = telemetry.stores.get()

        def fake_run(args, **kwargs):
            if "--version" in args:
                return subprocess.CompletedProcess(
                    args, 0, stdout="Hermes Agent v0.21.5\n", stderr=""
                )

            context = read_benchmark_context(kwargs["env"])
            self.assertIsNotNone(context)
            self.assertEqual(ctx.settings["mode"], "shadow")
            mode = read_benchmark_mode(kwargs["env"])
            self.assertIn(mode, {"off", "on"})
            turn_key = "turn-" + context.sample_id
            now = time.time()
            store.touch_turn(turn_key, mode, benchmark=context, now=now)
            store.increment_llm_request(turn_key)
            store.record_runtime_identity(
                turn_key,
                provider="synthetic-provider",
                requested_model="synthetic-model",
                response_model="synthetic-model-v1",
                api_mode="synthetic-api",
            )
            if mode == "off":
                store.increment_llm_request(turn_key)
                store.increment_tool_call(turn_key)
                store.increment_tool_call(turn_key)
                store.add_usage(
                    turn_key,
                    {"input_tokens": 1000, "output_tokens": 100},
                )
                store.record_turn_reason(turn_key, "mode_off")
                duration = 1.0
            else:
                store.increment_tool_call(turn_key)
                store.add_usage(
                    turn_key,
                    {"input_tokens": 800, "output_tokens": 90},
                )
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
                duration = 0.8
            store.finish_turn(turn_key, status="complete", now=now + duration)
            return subprocess.CompletedProcess(
                args, 0, stdout="Hermes Jev Performance\n", stderr=""
            )

        with self.credential_patch(), mock.patch(
            "jevperf.benchmark_runner.subprocess.run",
            side_effect=fake_run,
        ):
            report = run_live_benchmark(
                ctx,
                telemetry,
                repeats=2,
                warmups=1,
                include_network=False,
                fixture_path=fixture_path,
                executable="/synthetic/hermes",
                timeout_seconds=30,
            )

        self.assertEqual(ctx.settings["mode"], "shadow")
        self.assertEqual(report["run"]["status"], "complete")
        self.assertEqual(report["comparison"]["matched_pairs"], 2)
        duration = report["comparison"]["metrics"]["hermes_duration_ms"]
        self.assertLess(duration["on_mean"], duration["off_mean"])
        measured = [sample for sample in report["samples"] if not sample["is_warmup"]]
        self.assertTrue(all(sample["hermes_provider"] == "synthetic-provider" for sample in measured))
        self.assertTrue(all(sample["hermes_response_model"] == "synthetic-model-v1" for sample in measured))
        self.assertTrue(all(sample["hermes_api_mode"] == "synthetic-api" for sample in measured))
        self.assertEqual(telemetry.mode_changes, [])

    def test_timeout_records_failure_and_restores_original_mode(self):
        ctx, telemetry = self.make_runtime()
        fixture_path = self.make_fixture_file()

        def fake_run(args, **kwargs):
            if "--version" in args:
                return subprocess.CompletedProcess(
                    args, 0, stdout="Hermes Agent v0.21.5\n", stderr=""
                )
            raise subprocess.TimeoutExpired(args, 30)

        with self.credential_patch(), mock.patch(
            "jevperf.benchmark_runner.subprocess.run",
            side_effect=fake_run,
        ):
            report = run_live_benchmark(
                ctx,
                telemetry,
                repeats=2,
                warmups=0,
                fixture_path=fixture_path,
                executable="/synthetic/hermes",
                timeout_seconds=30,
            )

        self.assertEqual(ctx.settings["mode"], "shadow")
        self.assertEqual(report["run"]["status"], "complete_with_failures")
        self.assertEqual(report["comparison"]["matched_pairs"], 0)
        measured = [
            sample for sample in report["samples"]
            if not sample["is_warmup"]
        ]
        self.assertTrue(
            all(sample["status"] == "missing_telemetry" for sample in measured)
        )
        self.assertTrue(
            all(sample["error_category"] == "timeout" for sample in measured)
        )

    def test_wrong_on_route_is_excluded_and_marks_run_failed(self):
        ctx, telemetry = self.make_runtime()
        fixture_path = self.make_fixture_file()
        store = telemetry.stores.get()

        def fake_run(args, **kwargs):
            if "--version" in args:
                return subprocess.CompletedProcess(args, 0, stdout="Hermes Agent v0.21.5\n", stderr="")
            context = read_benchmark_context(kwargs["env"])
            mode = read_benchmark_mode(kwargs["env"])
            turn_key = "turn-" + context.sample_id
            now = time.time()
            store.touch_turn(turn_key, mode, benchmark=context, now=now)
            store.increment_llm_request(turn_key)
            if mode == "on":
                store.record_decision(
                    turn_key=turn_key,
                    mode="on",
                    decision=RoutingDecision(
                        family="web",
                        confidence=0.95,
                        accepted=True,
                        reason="accepted",
                        latency_ms=100,
                    ),
                    applied=False,
                    reason="no_family_tool",
                    now=now + 0.01,
                )
            else:
                store.record_turn_reason(turn_key, "mode_off")
            store.finish_turn(turn_key, status="complete", now=now + 0.2)
            return subprocess.CompletedProcess(args, 0, stdout="ok\n", stderr="")

        with self.credential_patch(), mock.patch(
            "jevperf.benchmark_runner.subprocess.run",
            side_effect=fake_run,
        ):
            report = run_live_benchmark(
                ctx,
                telemetry,
                repeats=2,
                warmups=0,
                fixture_path=fixture_path,
                executable="/synthetic/hermes",
                timeout_seconds=30,
            )

        self.assertEqual(report["run"]["status"], "complete_with_failures")
        self.assertEqual(report["comparison"]["matched_pairs"], 0)
        self.assertGreater(report["comparison"]["invalid_routing_samples"]["on"], 0)

    def test_live_benchmark_refuses_to_spend_without_telemetry(self):
        ctx, telemetry = self.make_runtime(telemetry_enabled=False)
        with self.credential_patch(), mock.patch(
            "jevperf.benchmark_runner.subprocess.run"
        ) as run:
            with self.assertRaisesRegex(RuntimeError, "telemetry_enabled"):
                run_live_benchmark(
                    ctx,
                    telemetry,
                    repeats=2,
                    warmups=0,
                    fixture_path=self.make_fixture_file(),
                    executable="/synthetic/hermes",
                )
        run.assert_not_called()

    def test_live_benchmark_refuses_to_spend_without_jev_credential(self):
        ctx, telemetry = self.make_runtime()
        with mock.patch(
            "jevperf.benchmark_runner.resolve_openrouter_credential",
            return_value=None,
        ), mock.patch("jevperf.benchmark_runner.subprocess.run") as run:
            with self.assertRaisesRegex(RuntimeError, "credential"):
                run_live_benchmark(
                    ctx,
                    telemetry,
                    repeats=2,
                    warmups=0,
                    fixture_path=self.make_fixture_file(),
                    executable="/synthetic/hermes",
                )
        run.assert_not_called()

    def test_live_benchmark_rejects_invalid_timeout_before_any_turn(self):
        ctx, telemetry = self.make_runtime()
        with self.credential_patch(), mock.patch(
            "jevperf.benchmark_runner.subprocess.run"
        ) as run:
            with self.assertRaisesRegex(ValueError, "between 10 and 3600"):
                run_live_benchmark(
                    ctx,
                    telemetry,
                    repeats=2,
                    warmups=0,
                    fixture_path=self.make_fixture_file(),
                    executable="/synthetic/hermes",
                    timeout_seconds=0,
                )
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
