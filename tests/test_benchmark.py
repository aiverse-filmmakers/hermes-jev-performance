import pathlib
import unittest

from jevperf.benchmark import (
    build_plan,
    calculate_comparison,
    capture_environment,
    fixture_set_hash,
    load_fixture_suite,
    run_synthetic_benchmark,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]


class BenchmarkTests(unittest.TestCase):
    def fixtures(self):
        return load_fixture_suite(
            ROOT / "benchmarks" / "fixtures" / "readonly_local.json",
            include_network=False,
        )

    def test_default_local_suite_is_read_only_and_network_free(self):
        fixtures = self.fixtures()
        self.assertGreaterEqual(len(fixtures), 4)
        self.assertTrue(all(fixture.read_only for fixture in fixtures))
        self.assertTrue(all(not fixture.requires_network for fixture in fixtures))

    def test_network_fixture_is_explicit_opt_in(self):
        without = self.fixtures()
        with_network = load_fixture_suite(
            ROOT / "benchmarks" / "fixtures" / "readonly_local.json",
            include_network=True,
        )
        self.assertGreater(len(with_network), len(without))
        self.assertTrue(any(fixture.requires_network for fixture in with_network))

    def test_plan_warms_both_modes_and_alternates_measured_order(self):
        fixtures = self.fixtures()[:1]
        plan = build_plan(fixtures, repeats=3, warmups=1, run_id="bench-test")
        warmups = [sample for sample in plan if sample.is_warmup]
        measured = [sample for sample in plan if not sample.is_warmup]

        self.assertEqual([sample.mode for sample in warmups], ["off", "on"])
        self.assertEqual(
            [sample.mode for sample in measured],
            ["off", "on", "on", "off", "off", "on"],
        )
        self.assertTrue(all(sample.run_id == "bench-test" for sample in plan))

    def test_repeats_requires_more_than_one_measured_pair(self):
        with self.assertRaises(ValueError):
            build_plan(self.fixtures(), repeats=1, warmups=1)

    def test_fixture_hash_is_deterministic(self):
        fixtures = self.fixtures()
        self.assertEqual(fixture_set_hash(fixtures), fixture_set_hash(fixtures))
        self.assertEqual(len(fixture_set_hash(fixtures)), 64)

    def test_comparison_excludes_warmups_and_pairs_by_fixture_repeat(self):
        samples = [
            {"fixture_id": "a", "family": "files", "repeat_index": 0, "mode": "off", "is_warmup": True, "status": "complete", "hermes_duration_ms": 9999},
            {"fixture_id": "a", "family": "files", "repeat_index": 0, "mode": "on", "is_warmup": True, "status": "complete", "route_family": "files", "route_applied": True, "hermes_duration_ms": 1},
            {"fixture_id": "a", "family": "files", "repeat_index": 0, "mode": "off", "is_warmup": False, "status": "complete", "hermes_duration_ms": 1000, "tool_calls": 4, "llm_requests": 2, "input_tokens": 1000, "output_tokens": 100},
            {"fixture_id": "a", "family": "files", "repeat_index": 0, "mode": "on", "is_warmup": False, "status": "complete", "route_family": "files", "route_applied": True, "hermes_duration_ms": 800, "tool_calls": 2, "llm_requests": 1, "input_tokens": 800, "output_tokens": 90},
            {"fixture_id": "a", "family": "files", "repeat_index": 1, "mode": "off", "is_warmup": False, "status": "complete", "hermes_duration_ms": 1200, "tool_calls": 4, "llm_requests": 2, "input_tokens": 1100, "output_tokens": 100},
            {"fixture_id": "a", "family": "files", "repeat_index": 1, "mode": "on", "is_warmup": False, "status": "complete", "route_family": "files", "route_applied": True, "hermes_duration_ms": 900, "tool_calls": 2, "llm_requests": 1, "input_tokens": 850, "output_tokens": 90},
        ]
        result = calculate_comparison(samples)
        duration = result["metrics"]["hermes_duration_ms"]

        self.assertEqual(result["matched_pairs"], 2)
        self.assertEqual(duration["off_mean"], 1100)
        self.assertEqual(duration["on_mean"], 850)
        self.assertEqual(duration["absolute_delta"], -250)
        self.assertAlmostEqual(duration["percent_change"], -22.7272727)
        self.assertEqual(result["invalid_routing_samples"]["on"], 0)

    def test_failed_half_pair_is_not_used_for_metric_deltas(self):
        samples = [
            {"fixture_id": "a", "family": "files", "repeat_index": 0, "mode": "off", "is_warmup": False, "status": "complete", "tool_calls": 3},
            {"fixture_id": "a", "family": "files", "repeat_index": 0, "mode": "on", "is_warmup": False, "status": "process_error", "tool_calls": 1},
        ]
        result = calculate_comparison(samples)
        self.assertEqual(result["matched_pairs"], 0)
        self.assertEqual(result["metrics"]["tool_calls"]["pairs"], 0)
        self.assertEqual(result["success_rate"]["off"], 1.0)
        self.assertEqual(result["success_rate"]["on"], 0.0)

    def test_on_fail_open_or_wrong_route_is_not_benchmark_evidence(self):
        samples = [
            {"fixture_id": "a", "family": "files", "repeat_index": 0, "mode": "off", "is_warmup": False, "status": "complete", "tool_calls": 3},
            {"fixture_id": "a", "family": "files", "repeat_index": 0, "mode": "on", "is_warmup": False, "status": "complete", "route_family": "web", "route_applied": False, "tool_calls": 1},
        ]
        result = calculate_comparison(samples)
        self.assertEqual(result["matched_pairs"], 0)
        self.assertEqual(result["successful_samples"]["on"], 0)
        self.assertEqual(result["invalid_routing_samples"]["on"], 1)

    def test_none_route_is_valid_without_hard_filter(self):
        samples = [
            {"fixture_id": "n", "family": "none", "repeat_index": 0, "mode": "off", "is_warmup": False, "status": "complete", "hermes_duration_ms": 100},
            {"fixture_id": "n", "family": "none", "repeat_index": 0, "mode": "on", "is_warmup": False, "status": "complete", "route_family": "none", "route_applied": False, "hermes_duration_ms": 110},
        ]
        result = calculate_comparison(samples)
        self.assertEqual(result["matched_pairs"], 1)

    def test_environment_metadata_has_no_host_user_or_path_fields(self):
        env = capture_environment(
            fixture_hash="a" * 64,
            repeats=3,
            warmups=1,
            provider="openrouter",
            jev_model="typesafe/jev-1.13",
            hermes_version="0.21.5",
        )
        forbidden = {"hostname", "username", "user", "cwd", "home", "ip", "mac"}
        self.assertTrue(forbidden.isdisjoint(env))
        self.assertEqual(env["fixture_set_sha256"], "a" * 64)

    def test_synthetic_ci_benchmark_makes_zero_network_calls(self):
        result = run_synthetic_benchmark(
            ROOT / "benchmarks" / "fixtures" / "ci_synthetic.json",
            repeats=3,
            warmups=1,
        )
        self.assertEqual(result["kind"], "synthetic_ci")
        self.assertEqual(result["network_calls"], 0)
        self.assertEqual(result["comparison"]["matched_pairs"], 9)
        duration = result["comparison"]["metrics"]["hermes_duration_ms"]
        self.assertLess(duration["percent_change"], 0)


if __name__ == "__main__":
    unittest.main()
