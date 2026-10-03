"""Real Hermes contract tests, run explicitly by verify_native_compaction.py."""
import json
from pathlib import Path
import tempfile
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
        self.ctx = FakeContext({"compaction_mode": "on", "mode": "shadow", "telemetry_enabled": False})
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
        rejected = json.loads(self.engine.handle_tool_call("jev_recover", {"reference": ref}, messages=transcript()))
        self.assertIn("error", rejected)
        # A fresh engine can recover a persisted reference without an in-memory allowlist.
        resumed = self.engine.clone_for_agent()
        resumed.jev_archive = OutputArchive(self.archive.root)
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
        page = json.loads(resumed.handle_tool_call("jev_recover", {"reference": ref, "limit": 20000}, messages=restored))
        self.assertEqual(page["text"], original[4]["content"][:20000])


if __name__ == "__main__":
    unittest.main()
