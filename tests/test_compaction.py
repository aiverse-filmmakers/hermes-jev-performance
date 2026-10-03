import copy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from jevperf.compaction import (JevCompactor, STUB_PREFIX, build_state, candidates_for,
                                estimated_tokens, preview, questions_for)
from jevperf.compaction_archive import OutputArchive
from jevperf.compaction_config import CompactionConfig, read_compaction_config
from jevperf.compaction_metrics import compaction_summary, record_compaction
from jevperf.commands import handle_jev_command
from jevperf.families import filter_tools
from tests.fakes import FakeContext


def transcript(outputs=1):
    rows = [{"role": "system", "content": "Help with the task."},
            {"role": "user", "content": "Audit config and logs; keep exact configuration values."},
            {"role": "assistant", "content": "I will inspect both."}]
    for i in range(outputs):
        cid = f"call-{i}"
        rows.extend([
            {"role": "assistant", "content": "", "tool_calls": [{"id": cid, "type": "function",
             "function": {"name": "read_file", "arguments": '{"path":"logs/synthetic.log"}'}}]},
            {"role": "tool", "tool_call_id": cid,
             "content": "\n".join(f"line {j} INFO stable synthetic record" for j in range(1500))},
        ])
    rows += [{"role": "assistant", "content": "Log reviewed."},
             {"role": "user", "content": "Now compare the latest config."}]
    rows += [{"role": "assistant", "content": f"recent {i}"} for i in range(5)]
    return rows


class Evaluator:
    def __init__(self, probability=0.99, fail=None):
        self.probability, self.fail, self.calls = probability, fail, []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise self.fail
        return {"model": "typesafe/jev-1.13", "usage": {"cost": 0.00001, "input_tokens": 10, "output_tokens": 1},
                "answers": {k: {"type": "noul", "noul": self.probability} for k in kwargs["questions"]}}


def compactor(evaluator=None, **kwargs):
    credential = mock.Mock(token="synthetic", name="synthetic")
    return JevCompactor(evaluator=evaluator or Evaluator(), credential_resolver=lambda: credential, **kwargs)


class CompactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/private/tmp" if Path("/private/tmp").exists() else None)
        self.addCleanup(self.temp.cleanup)
        self.archive = OutputArchive(Path(self.temp.name) / "archive")
        self.config = CompactionConfig(mode="on")

    def run_compaction(self, rows=None, engine=None, config=None, **kwargs):
        return (engine or compactor()).compact(rows or transcript(), config=config or self.config,
            model="typesafe/jev-1.13", timeout=2.5, archive=self.archive, session_id="synthetic-session", **kwargs)

    def test_off_makes_no_calls_or_writes(self):
        evaluator = Evaluator()
        rows = transcript()
        result = self.run_compaction(rows, compactor(evaluator), replace(self.config, mode="off"))
        self.assertIs(result.messages, rows)
        self.assertEqual(evaluator.calls, [])
        self.assertFalse(self.archive.root.exists())

    def test_shadow_predicts_without_changing_transcript_or_writing(self):
        rows = transcript()
        original = copy.deepcopy(rows)
        out = self.run_compaction(rows, config=replace(self.config, mode="shadow"))
        self.assertEqual(out.outcome, "shadow")
        self.assertIs(out.messages, rows)
        self.assertEqual(rows, original)
        self.assertLess(out.estimated_tokens_after, out.estimated_tokens_before)
        self.assertFalse(self.archive.root.exists())

    def test_outputs_recover_verbatim_after_fresh_archive_instance(self):
        rows = transcript(2)
        original = copy.deepcopy(rows)
        out = self.run_compaction(rows)
        self.assertEqual(out.outcome, "applied")
        self.assertEqual(rows, original)
        self.assertEqual(len(out.messages), len(rows))
        for old, new in zip(rows, out.messages):
            if old["role"] != "tool":
                self.assertIs(old, new)
            else:
                reference = new["content"].split(STUB_PREFIX, 1)[1].split(";", 1)[0]
                drawer = OutputArchive(self.archive.root)
                text, offset = "", 0
                while offset is not None:
                    page = drawer.recover(reference, offset=offset, limit=700)
                    text += page["text"]
                    offset = page["next_offset"]
                self.assertEqual(text, old["content"])
                self.assertEqual(new["tool_call_id"], old["tool_call_id"])

    def test_low_confidence_and_invalid_answers_keep_everything(self):
        for p in (0.5, float("nan"), 1.1, True):
            rows = transcript()
            out = self.run_compaction(rows, compactor(Evaluator(p)))
            self.assertIs(out.messages, rows)
        self.assertFalse(self.archive.root.exists())

    def test_small_recent_orphan_duplicate_and_multimodal_outputs_are_protected(self):
        rows = transcript()
        rows[4]["content"] = "SHARD_COUNT=13"
        self.assertEqual(candidates_for(rows, self.config), [])
        rows[4]["content"] = [{"type": "image_url", "image_url": {"url": "synthetic"}}]
        self.assertEqual(candidates_for(rows, self.config), [])
        rows = transcript()
        rows[3]["tool_calls"][0]["id"] = "different"
        self.assertEqual(candidates_for(rows, self.config), [])
        rows = transcript()
        rows.insert(5, dict(rows[4]))
        self.assertEqual(candidates_for(rows, self.config), [])
        rows = transcript()
        rows[4]["is_error"] = True
        self.assertEqual(candidates_for(rows, self.config), [])

    def test_recent_full_exchange_protected_even_when_call_precedes_tail_cut(self):
        rows = transcript()
        rows.insert(3, {"role": "user", "content": "current task"})
        rows = rows[:7] + [{"role": "assistant", "content": "tail"}] * 3
        self.assertEqual(candidates_for(rows, self.config), [])

    def test_archive_failure_provider_failure_and_small_savings_preserve_input(self):
        rows = transcript()
        with mock.patch.object(self.archive, "write_batch", side_effect=OSError()):
            self.assertIs(self.run_compaction(rows).messages, rows)
        self.assertIs(self.run_compaction(rows, compactor(Evaluator(fail=TimeoutError()))).messages, rows)
        self.assertEqual(self.run_compaction(rows, target_tokens=1).outcome, "still_over_budget")
        config = replace(self.config, min_reduction_ratio=0.95)
        rows[1]["content"] = "essential user text " * 10000
        self.assertEqual(self.run_compaction(rows, config=config).outcome, "insufficient_reduction")

    def test_batching_respects_request_budget_and_question_limit(self):
        rows = transcript(140)
        evaluator = Evaluator()
        config = replace(self.config, max_request_tokens=3000, max_state_tokens=1000, preview_chars=100)
        # Large state fails safely; no request escapes the budget.
        result = self.run_compaction(rows, compactor(evaluator), config)
        self.assertIs(result.messages, rows)
        self.assertEqual(evaluator.calls, [])
        rows = transcript(10)
        config = replace(self.config, max_request_tokens=3000, max_state_tokens=1500, preview_chars=100)
        result = self.run_compaction(rows, compactor(evaluator), config)
        self.assertEqual(result.outcome, "applied")
        self.assertGreater(len(evaluator.calls), 1)
        for call in evaluator.calls:
            self.assertLessEqual(estimated_tokens({"state": call["state"], "questions": call["questions"]}) + 128, 3000)
            self.assertLessEqual(len(call["questions"]), 128)

    def test_previews_show_both_ends_and_do_not_send_tool_arguments(self):
        rows = transcript()
        rows[3]["tool_calls"][0]["function"]["arguments"] = "PRIVATE_ARGUMENT_VALUE"
        candidate = candidates_for(rows, self.config)[0]
        question = questions_for(candidate, self.config)
        self.assertIn("line 0 INFO", question["instructions"])
        self.assertIn("line 1499 INFO", question["instructions"])
        state = build_state(rows, self.config)
        self.assertNotIn("PRIVATE_ARGUMENT_VALUE", json.dumps(state))
        self.assertEqual(preview("short", 100), "short")

    def test_repeated_compaction_does_not_archive_stubs(self):
        out = self.run_compaction()
        evaluator = Evaluator()
        again = self.run_compaction(out.messages, compactor(evaluator))
        self.assertEqual(again.outcome, "no_candidates")
        self.assertEqual(evaluator.calls, [])

    def test_drawer_integrity_permissions_and_path_confinement(self):
        ref = self.archive.reference("session")
        self.archive.write_batch([(ref, "exact output")])
        self.assertEqual(self.archive.recover(ref)["text"], "exact output")
        self.assertEqual((self.archive.root.stat().st_mode & 0o777), 0o700)
        path = self.archive.root / (ref + ".txt")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        path.write_text("tampered")
        with self.assertRaises(ValueError):
            self.archive.recover(ref)
        for invalid in ("../secret", "/absolute", ref + "/../x"):
            with self.assertRaises(ValueError):
                self.archive.recover(invalid)
        for kwargs in ({"offset": -1}, {"limit": 50000}, {"offset": True}):
            with self.assertRaises(ValueError):
                self.archive.recover(ref, **kwargs)

    def test_symlink_drawer_rejected(self):
        target = Path(self.temp.name) / "elsewhere"
        target.mkdir()
        self.archive.root.symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.archive.write_batch([(self.archive.reference("session"), "exact")])
        self.assertEqual(list(target.iterdir()), [])

    def test_deadline_budget_and_no_unbounded_extra_batches(self):
        evaluator = Evaluator()
        ticks = iter([0, 0, 50, 50, 50])
        result = self.run_compaction(engine=compactor(evaluator, clock=lambda: next(ticks)))
        self.assertEqual(result.outcome, "deadline")
        self.assertFalse(self.archive.root.exists())

    def test_configuration_control_and_recovery_tool_preservation(self):
        ctx = FakeContext()
        self.assertEqual(read_compaction_config(ctx).mode, "off")
        self.assertIn("SHADOW", handle_jev_command(ctx, "compaction shadow"))
        self.assertEqual(read_compaction_config(ctx).mode, "shadow")
        ctx.settings["compaction_drop_confidence"] = float("nan")
        self.assertEqual(read_compaction_config(ctx).mode, "off")
        tools = [{"name": "web_search"}, {"name": "terminal"}, {"name": "jev_recover"}]
        filtered, _, _ = filter_tools(tools, "web")
        self.assertIn({"name": "jev_recover"}, filtered)

    def test_metrics_accept_only_content_free_allowlisted_fields(self):
        path = Path(self.temp.name) / "metrics.sqlite3"
        metadata = self.run_compaction().metadata()
        metadata["prompt"] = "PRIVATE_PROMPT_VALUE"
        record_compaction(metadata, path)
        self.assertNotIn(b"PRIVATE_PROMPT_VALUE", path.read_bytes())
        summary = compaction_summary(path)
        self.assertEqual(summary["applied"], 1)
        self.assertGreater(summary["estimated_tokens_saved"], 0)
        self.assertAlmostEqual(summary["cost_usd"], 0.00001)


if __name__ == "__main__":
    unittest.main()
