"""Real Hermes contract tests, run explicitly by verify_native_compaction.py."""
import json
import sqlite3
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from agent.context_compressor import ContextCompressor
from agent.context_engine import ContextEngine
from jevperf.compaction import STUB_PREFIX
from jevperf.compaction_archive import OutputArchive
from jevperf.context_engine import create_context_engine
from tests.fakes import FakeContext
from tests.test_compaction import Evaluator, compactor, transcript


class NativeCompactionContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.archive = OutputArchive(self.root / "archive")
        self.ctx = FakeContext({"compaction_mode": "on", "compaction_allow_external": True,
                                "mode": "shadow", "telemetry_enabled": False})
        with mock.patch("hermes_cli.config.load_config_readonly", return_value={}):
            self.engine = create_context_engine(self.ctx, compactor=compactor(), archive=self.archive)
        self.engine.update_model(model="synthetic-model", context_length=100000)
        self.engine.bind_session_state(session_id="synthetic-session")

    def test_real_context_engine_and_isolated_clone(self):
        self.assertIsInstance(self.engine, ContextEngine)
        child = self.engine.clone_for_agent()
        child.update_model(model="synthetic-child", context_length=200000)
        self.assertEqual(self.engine.context_length, 100000)
        self.assertEqual(child.context_length, 200000)
        self.assertEqual(child.compression_count, 0)
        self.assertIn("jev_recover", [t["name"] for t in child.get_tool_schemas()])

    def test_keeps_multi_call_ids_and_removes_stale_result_sidecars(self):
        rows = transcript(2)
        # One assistant message carries both calls, matching Hermes' multi-tool shape.
        rows[3]["tool_calls"].extend(rows[5]["tool_calls"])
        del rows[5]
        for row in rows:
            row["_db_persisted"] = True
        rows[4]["api_content"] = rows[4]["content"]
        with mock.patch.object(ContextCompressor, "compress", side_effect=AssertionError("unexpected summary call")):
            out = self.engine.compress(rows, current_tokens=20000)
        self.assertEqual(self.engine.compression_count, 1)
        self.assertEqual(out[3]["tool_calls"], rows[3]["tool_calls"])
        self.assertNotIn("api_content", out[4])
        self.assertTrue(all("_db_persisted" not in m for m in out))
        self.assertTrue(out[4]["content"].startswith(STUB_PREFIX))
        self.assertEqual(rows[4]["api_content"], rows[4]["content"])

    def test_off_shadow_and_provider_failure_use_normal_compressor_once(self):
        for settings in ({"mode": "off", "compaction_mode": "on"},
                         {"mode": "shadow", "compaction_mode": "off"},
                         {"mode": "shadow", "compaction_mode": "shadow"}):
            self.ctx.settings.update(settings)
            rows = transcript()
            with mock.patch.object(ContextCompressor, "compress", return_value=rows) as normal:
                out = self.engine.compress(rows, focus_topic="config", force=True, memory_context="memory")
            self.assertIs(out, rows)
            normal.assert_called_once()
        self.assertFalse(self.archive.root.exists())
        self.ctx.settings.update(mode="shadow", compaction_mode="on")
        self.engine.jev_compactor = compactor(Evaluator(fail=RuntimeError("synthetic failure")))
        with mock.patch.object(ContextCompressor, "compress", return_value=transcript()) as normal:
            self.engine.compress(transcript())
        normal.assert_called_once()

    def test_recovery_requires_reference_in_actual_conversation(self):
        out = self.engine.compress(transcript())
        ref = out[4]["content"].split(STUB_PREFIX, 1)[1].split(";", 1)[0]
        payload = json.loads(self.engine.handle_tool_call("jev_recover", {"reference": ref}, messages=out))
        self.assertIn("line 0 INFO", payload["text"])
        # Authorization survives loss of the transcript carrier.
        self.assertEqual(payload, json.loads(self.engine.handle_tool_call("jev_recover", {"reference": ref}, messages=[])))
        foreign = self.engine.clone_for_agent()
        foreign.jev_archive = self.archive
        foreign.bind_session_state(session_id="different-session")
        rejected = json.loads(foreign.handle_tool_call("jev_recover", {"reference": ref}, messages=out))
        self.assertIn("error", rejected)
        # A fresh engine can recover a persisted reference without an in-memory allowlist.
        resumed = self.engine.clone_for_agent()
        resumed.jev_archive = OutputArchive(self.archive.root)
        resumed.bind_session_state(session_id="synthetic-session")
        self.assertEqual(payload, json.loads(resumed.handle_tool_call("jev_recover", {"reference": ref}, messages=out)))

    def test_real_engine_discovery_collector(self):
        from plugins.context_engine import _EngineCollector
        from jevperf.plugin import register_plugin
        collector = _EngineCollector()
        register_plugin(collector)
        self.assertIsInstance(collector.engine, ContextEngine)
        self.assertEqual(collector.engine.name, "hermes-jev-performance")

    def test_hermes_session_store_roundtrip_and_concurrent_append(self):
        from hermes_state import SessionDB
        db = SessionDB(self.root / "state.db")
        self.addCleanup(db.close)
        db.create_session("synthetic-session", "cli")
        original = transcript()
        db.append_messages_batch("synthetic-session", original)
        watermark = db.get_active_message_watermark("synthetic-session")
        out = self.engine.compress(original)
        db.append_messages_batch("synthetic-session", [{"role": "user", "content": "arrived concurrently"}])
        db.archive_and_compact("synthetic-session", out, watermark=watermark)
        restored = db.get_messages_as_conversation("synthetic-session")
        self.assertEqual(restored[-1]["content"], "arrived concurrently")
        labels = [m for m in restored if m.get("role") == "tool" and m.get("content", "").startswith(STUB_PREFIX)]
        self.assertEqual(len(labels), 1)
        ref = labels[0]["content"].split(STUB_PREFIX, 1)[1].split(";", 1)[0]
        resumed = self.engine.clone_for_agent()
        resumed.jev_archive = OutputArchive(self.archive.root)
        resumed.bind_session_state(db, "synthetic-session")
        page = json.loads(resumed.handle_tool_call("jev_recover", {"reference": ref, "limit": 20000}, messages=restored))
        self.assertEqual(page["text"], original[4]["content"][:20000])

    def test_actual_normal_summarization_preserves_recovery_after_resume(self):
        # Execute real compression assembly/window/provenance handling. Stub only
        # the paid provider boundary, with a summary that omits all Jev references.
        compacted = self.engine.compress(transcript())
        ref = compacted[4]["content"].split(STUB_PREFIX, 1)[1].split(";", 1)[0]
        rows = compacted + [row for i in range(20) for row in (
            {"role": "user", "content": f"Audit continuation {i}: " + "synthetic detail " * 200},
            {"role": "assistant", "content": "The audit remains in progress. " * 100})]
        self.ctx.settings["compaction_mode"] = "off"
        self.engine.protect_first_n = 3
        self.engine.protect_last_n = 4
        self.engine.tail_token_budget = 300
        summary = "## User request\nUser asked to audit configuration and logs. Keep exact configuration values.\n## Progress\nAudit in progress."
        response = SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=summary, reasoning_content=None), finish_reason="stop")], usage=None)
        with mock.patch("agent.context_compressor.call_llm", return_value=response) as provider:
            out = self.engine.compress(rows, force=True, current_tokens=50000)
        provider.assert_called_once()
        self.assertLess(len(out), len(rows))
        self.assertFalse(any(m.get("role") == "tool" and m.get("content", "").startswith(STUB_PREFIX + ref) for m in out))
        self.assertTrue(any(ref in m.get("content", "") for m in out))
        resumed = self.engine.clone_for_agent()
        resumed.jev_archive = OutputArchive(self.archive.root)
        resumed.bind_session_state(session_id="synthetic-session")
        recovered = json.loads(resumed.handle_tool_call("jev_recover", {"reference": ref}, messages=out))
        self.assertEqual(recovered["text"], transcript()[4]["content"][:20000])

    def test_host_tail_commit_does_not_recall_carried_output_twice(self):
        from hermes_state import SessionDB
        db = SessionDB(self.root / "recall.db")
        self.addCleanup(db.close)
        db.create_session("synthetic-session", "cli")
        original = transcript()
        db.append_messages_batch("synthetic-session", original)
        rows = db.get_messages_as_conversation("synthetic-session")
        self.engine.bind_session_state(db, "synthetic-session")
        out = self.engine.compress(rows)
        changed_index = 4
        carried = [m for m in out if m.pop("_compaction_tail", False)]
        self.assertEqual(len(carried), len(rows) - changed_index - 1)
        self.assertNotIn(out[changed_index], carried)
        # This is the actual host persistence contract: the tagged contiguous
        # suffix is passed as tail_count, and old modified output remains archived.
        db.archive_and_compact("synthetic-session", out, tail_count=len(carried))
        with sqlite3.connect(self.root / "recall.db") as connection:
            counts = connection.execute(
                "SELECT active, compacted, COUNT(*) FROM messages WHERE session_id=? AND content=? GROUP BY active, compacted",
                ("synthetic-session", original[8]["content"])).fetchall()
        visible = sum(row[2] for row in counts if row[0] or row[1])
        # The unchanged short baseline has one active copy. Its old carried
        # original is superseded and must not become a second recall result.
        self.assertEqual(visible, 1)

    def test_stale_attempt_cannot_publish_diagnostics_metrics_or_archives(self):
        metrics = mock.Mock()
        with mock.patch("hermes_cli.config.load_config_readonly", return_value={}):
            engine = create_context_engine(self.ctx, compactor=compactor(), archive=self.archive, metrics_recorder=metrics)
        engine.update_model(model="synthetic-model", context_length=100000)
        engine.bind_session_state(session_id="synthetic-session")
        engine._compression_cancelled_check = lambda: True
        rows = transcript()
        self.assertIs(engine.compress(rows), rows)
        self.assertIsNone(engine.jev_last_result)
        self.assertEqual(engine.compression_count, 0)
        metrics.assert_not_called()
        self.assertFalse(self.archive.root.exists())

    def test_actual_agent_compression_commit_preserves_tail_recall(self):
        from hermes_state import SessionDB
        from run_agent import AIAgent
        from agent.conversation_compression import compress_context
        db = SessionDB(self.root / "agent-recall.db")
        self.addCleanup(db.close)
        db.create_session("synthetic-session", "cli")
        original = transcript()
        db.append_messages_batch("synthetic-session", original)
        rows = db.get_messages_as_conversation("synthetic-session")
        agent = AIAgent(api_key="synthetic", base_url="https://provider.example/v1", model="synthetic-model",
                        quiet_mode=True, session_db=db, session_id="synthetic-session",
                        skip_context_files=True, skip_memory=True)
        agent.context_compressor = self.engine
        agent.compression_in_place = True
        agent._compression_feasibility_checked = True
        agent._cached_system_prompt = "Help with the synthetic audit."
        self.engine.bind_session_state(db, "synthetic-session")
        out, _ = compress_context(agent, rows, "Help with the synthetic audit.", approx_tokens=60000)
        self.assertTrue(agent._last_compression_attempt_in_place)
        self.assertTrue(out[4]["content"].startswith(STUB_PREFIX))
        self.assertTrue(all(m.get("_db_persisted") for m in out))
        with sqlite3.connect(self.root / "agent-recall.db") as connection:
            counts = connection.execute(
                "SELECT active, compacted, COUNT(*) FROM messages WHERE session_id=? AND content=? GROUP BY active, compacted",
                ("synthetic-session", original[8]["content"])).fetchall()
        self.assertEqual(sum(row[2] for row in counts if row[0] or row[1]), 1)

    def test_bound_session_authorization_survives_real_compression_rotation(self):
        from hermes_state import SessionDB
        db = SessionDB(self.root / "rotation.db")
        self.addCleanup(db.close)
        db.create_session("synthetic-session", "cli")
        out = self.engine.compress(transcript())
        ref = out[4]["content"].split(STUB_PREFIX, 1)[1].split(";", 1)[0]
        db.end_session("synthetic-session", "compression")
        db.create_session("synthetic-child", "cli", parent_session_id="synthetic-session")
        self.engine.bind_session_state(db, "synthetic-child")
        recovered = json.loads(self.engine.handle_tool_call("jev_recover", {"reference": ref}, messages=[]))
        self.assertEqual(recovered["text"], transcript()[4]["content"][:20000])
        # An unrelated child/fork is not the host's compression continuation.
        db.create_session("unrelated-child", "delegate", parent_session_id="synthetic-session")
        self.engine.bind_session_state(db, "unrelated-child")
        rejected = json.loads(self.engine.handle_tool_call("jev_recover", {"reference": ref}, messages=out))
        self.assertIn("error", rejected)


if __name__ == "__main__":
    unittest.main()
