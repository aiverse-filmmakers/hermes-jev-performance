import os
import sqlite3
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from jevperf.benchmark_context import (
    FIXTURE_ID_ENV,
    RUN_ID_ENV,
    SAMPLE_ID_ENV,
    WARMUP_ENV,
)
from jevperf.routing import RoutingDecision
from jevperf.store import StoreProvider
from jevperf.telemetry import TelemetryObserver
from tests.fakes import FakeContext


class TelemetryTests(unittest.TestCase):
    def make_observer(self):
        temp = tempfile.TemporaryDirectory()
        path = Path(temp.name) / "metrics.sqlite3"
        provider = StoreProvider(lambda: path)
        observer = TelemetryObserver(
            FakeContext({"mode": "on", "telemetry_enabled": True}),
            stores=provider,
        )
        self.addCleanup(temp.cleanup)
        return observer, path

    def test_hook_metadata_aggregation_ignores_content(self):
        observer, path = self.make_observer()

        observer.on_pre_api_request(
            session_id="private-session",
            turn_id="private-turn",
            user_message="SECRET_PROMPT_MARKER",
            conversation_history=["SECRET_HISTORY_MARKER"],
            request={"messages": ["SECRET_REQUEST_MARKER"]},
        )
        observer.record_decision(
            session_id="private-session",
            turn_id="private-turn",
            mode="on",
            decision=RoutingDecision(
                family="web",
                confidence=0.95,
                accepted=True,
                reason="accepted",
                latency_ms=250,
                cost_usd=0.00002,
                input_tokens=90,
                output_tokens=9,
            ),
            applied=True,
            reason="filtered",
        )
        observer.on_post_api_request(
            session_id="private-session",
            turn_id="private-turn",
            usage={"input_tokens": 1000, "output_tokens": 100},
            response={"content": "SECRET_RESPONSE_MARKER"},
            assistant_message="SECRET_ASSISTANT_MARKER",
        )
        observer.on_post_tool_call(
            session_id="private-session",
            turn_id="private-turn",
            tool_name="web_search",
            args={"query": "SECRET_TOOL_ARG_MARKER"},
            result="SECRET_TOOL_RESULT_MARKER",
            error_message="SECRET_ERROR_MARKER",
        )
        observer.on_session_end(
            session_id="private-session",
            turn_id="private-turn",
            completed=True,
            failed=False,
            interrupted=False,
        )

        stats = observer.summary()
        self.assertEqual(stats.turns, 1)
        self.assertEqual(stats.decisions, 1)
        self.assertEqual(stats.applied, 1)
        self.assertEqual(stats.avg_tool_calls, 1)
        self.assertEqual(stats.avg_llm_requests, 1)
        self.assertEqual(stats.input_tokens, 1000)
        self.assertEqual(stats.output_tokens, 100)

        raw = path.read_bytes()
        for marker in (
            b"SECRET_PROMPT_MARKER",
            b"SECRET_HISTORY_MARKER",
            b"SECRET_REQUEST_MARKER",
            b"SECRET_RESPONSE_MARKER",
            b"SECRET_ASSISTANT_MARKER",
            b"SECRET_TOOL_ARG_MARKER",
            b"SECRET_TOOL_RESULT_MARKER",
            b"SECRET_ERROR_MARKER",
            b"private-session",
            b"private-turn",
        ):
            self.assertNotIn(marker, raw)

    def test_disabled_telemetry_creates_no_database(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "metrics.sqlite3"
        observer = TelemetryObserver(
            FakeContext({"telemetry_enabled": False}),
            stores=StoreProvider(lambda: path),
        )
        observer.on_pre_api_request(session_id="s", turn_id="t")
        observer.on_post_tool_call(session_id="s", turn_id="t")
        observer.on_session_end(session_id="s", turn_id="t", completed=True)
        self.assertFalse(path.exists())

    def test_hook_failures_are_swallowed(self):
        class BrokenStore:
            path = Path("/synthetic/broken")

            def touch_turn(self, *args, **kwargs):
                raise RuntimeError("broken")

            def cleanup(self, *args, **kwargs):
                raise RuntimeError("broken")

        class BrokenProvider:
            def get(self):
                return BrokenStore()

        observer = TelemetryObserver(FakeContext(), stores=BrokenProvider())
        self.assertIsNotNone(observer.start_turn("s", "t"))

    def test_explicit_benchmark_env_tags_turn_without_content(self):
        observer, path = self.make_observer()
        env = {
            RUN_ID_ENV: "bench-safe",
            SAMPLE_ID_ENV: "sample-safe",
            FIXTURE_ID_ENV: "files-read-readme-heading",
            WARMUP_ENV: "0",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            observer.on_pre_api_request(
                session_id="private-session",
                turn_id="private-turn",
                user_message="BENCHMARK_PROMPT_MUST_NOT_PERSIST",
            )
            observer.on_session_end(
                session_id="private-session",
                turn_id="private-turn",
                completed=True,
                failed=False,
                interrupted=False,
            )

        with sqlite3.connect(path) as con:
            row = con.execute(
                """
                SELECT benchmark_run_id, benchmark_sample_id,
                       benchmark_fixture_id, benchmark_warmup
                FROM hermes_turns
                """
            ).fetchone()
        self.assertEqual(
            row,
            ("bench-safe", "sample-safe", "files-read-readme-heading", 0),
        )
        raw = path.read_bytes()
        self.assertNotIn(b"BENCHMARK_PROMPT_MUST_NOT_PERSIST", raw)
        self.assertNotIn(b"private-session", raw)
        self.assertNotIn(b"private-turn", raw)

if __name__ == "__main__":
    unittest.main()
