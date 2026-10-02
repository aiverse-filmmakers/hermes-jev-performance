import unittest

from jevperf.benchmark_context import (
    FIXTURE_ID_ENV,
    RUN_ID_ENV,
    SAMPLE_ID_ENV,
    WARMUP_ENV,
    BenchmarkContext,
    benchmark_env,
    read_benchmark_context,
)


class BenchmarkContextTests(unittest.TestCase):
    def test_round_trip_safe_context(self):
        context = BenchmarkContext(
            run_id="bench-abc",
            sample_id="sample-def",
            fixture_id="files-read-readme-heading",
            is_warmup=True,
        )
        parsed = read_benchmark_context(benchmark_env(context))
        self.assertEqual(parsed, context)

    def test_partial_context_is_ignored(self):
        self.assertIsNone(read_benchmark_context({RUN_ID_ENV: "bench-a"}))

    def test_unsafe_identifier_is_rejected(self):
        env = {
            RUN_ID_ENV: "bench-a",
            SAMPLE_ID_ENV: "sample-a",
            FIXTURE_ID_ENV: "../private/path",
            WARMUP_ENV: "0",
        }
        self.assertIsNone(read_benchmark_context(env))


if __name__ == "__main__":
    unittest.main()
