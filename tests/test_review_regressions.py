"""Behavioral regressions for the routing/privacy and compaction review."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from jevperf.compaction import candidates_for, build_state, STUB_PREFIX
from jevperf.compaction_archive import OutputArchive
from jevperf.compaction_config import CompactionConfig, read_compaction_config
from jevperf.compaction_metrics import record_compaction, compaction_summary
from jevperf.families import filter_tools, tool_name
from jevperf.middleware import RoutingMiddleware
from jevperf.turns import extract_routing_state, redact_routing_state, TurnDecisionCache
from tests.fakes import FakeContext
from tests.test_middleware import FakeRouter, request, tool
from tests import test_middleware as middleware_fixtures
from tests.test_compaction import compactor, transcript, Evaluator


class RoutingReviewTests(unittest.TestCase):
    def setUp(self):
        self.ctx = FakeContext({"mode": "on"})
        self.router = FakeRouter(middleware_fixtures.MiddlewareTests().decision())
        self.cache = TurnDecisionCache()
        self.mw = RoutingMiddleware(self.ctx, router=self.router, cache=self.cache)

    def route(self, req):
        return self.mw(request=req, session_id="synthetic-session", turn_id="synthetic-turn")

    def test_empty_injected_cache_is_used(self):
        self.assertIs(self.mw.cache, self.cache)
        self.route(request())
        self.assertEqual(len(self.cache), 1)

    def test_json_env_and_quoted_multiword_secrets_are_fully_redacted(self):
        samples = [
            '{"password": "synthetic two word value", "task": "search the web"}',
            "OPENROUTER_API_KEY=synthetic-value search the web",
            "password='synthetic two word value' search the web",
            'password="synthetic \\"quoted\\" value" search the web',
            '{"auth": {"credentials": {"nested": "synthetic-value"}}, "task": "search"}',
            'client_secret="synthetic-value" search the web',
            'Inspect https://synthetic-user:synthetic-value@example.com/page',
        ]
        for text in samples:
            with self.subTest(text=text):
                state = extract_routing_state({"input": text})
                self.assertIsNotNone(state)
                for value in ("synthetic-value", "two word value", "quoted", "synthetic-user"):
                    self.assertNotIn(value, state)
                self.assertIn("<REDACTED>", state)

    def test_broader_tokens_are_removed(self):
        for prefix in ("sk-or-v1-", "ghp_", "github_pat_", "xoxb-"):
            token = prefix + "A" * 30
            self.assertNotIn(token, redact_routing_state("Search docs using " + token))

    def test_uncertain_secret_formats_skip_transmission_in_both_modes(self):
        for mode in ("on", "shadow"):
            self.ctx.settings["mode"] = mode
            for text in ('password="unfinished synthetic value',
                         "the password is synthetic two word value",
                         "password=synthetic two word value",
                         "-----BEGIN " + "PRIVATE KEY-----\nsynthetic bytes",
                         'Use credentials={"nested":"synthetic-value"} to research'):
                req = request()
                req["messages"][-1]["content"] = text
                self.assertIsNone(self.route(req))
        self.assertEqual(self.router.calls, [])

    def test_new_user_instruction_same_turn_invalidates_web_route(self):
        req = request()
        self.assertIsNotNone(self.route(req))
        self.router.decision = middleware_fixtures.MiddlewareTests().decision("terminal")
        req["messages"].append({"role": "user", "content": "Now edit the local files and execute their validation commands."})
        self.assertIsNone(self.route(req))
        self.assertIn("terminal", [tool_name(t) for t in req["tools"]])
        self.assertEqual(len(self.router.calls), 1)
        self.route(req)
        self.assertEqual(len(self.router.calls), 1)
        self.assertIsNone(self.route(request()))
        # A genuinely new turn can classify the new complete instruction.
        self.mw(request=req, session_id="synthetic-session", turn_id="next-turn")
        self.assertEqual(len(self.router.calls), 2)

    def test_changed_confidence_and_provider_settings_invalidate_cache(self):
        self.route(request())
        self.ctx.settings["min_confidence"] = 0.99
        self.router.decision = middleware_fixtures.MiddlewareTests().decision(confidence=0.95, accepted=False)
        self.assertIsNone(self.route(request()))
        self.assertEqual(len(self.router.calls), 1)
        self.mw(request=request(), session_id="synthetic-session", turn_id="next-turn")
        self.assertEqual(self.router.calls[-1][1]["min_confidence"], 0.99)
        for key, value in (("model", "synthetic-other-model"), ("provider", "synthetic-other-provider"),
                           ("timeout_seconds", 1.0), ("mode", "shadow")):
            before = len(self.router.calls)
            self.ctx.settings[key] = value
            self.route(request())
            self.assertEqual(len(self.router.calls), before)

    def test_image_only_empty_and_captioned_images_do_not_reuse_old_route(self):
        self.route(request())
        for content in ([], "", [{"type": "image_url", "image_url": {"url": "synthetic"}}],
                        [{"type": "text", "text": "Search the web"}, {"type": "input_image", "image_url": "synthetic"}]):
            req = request()
            req["messages"].append({"role": "user", "content": content})
            req["input"] = "old request from another API field"
            self.assertIsNone(self.route(req))
            self.assertIsNone(self.mw.last_decision)
        self.assertEqual(len(self.router.calls), 1)

    def test_short_followup_and_truncated_suffix_fail_open_without_history_transmission(self):
        for text in ("k finish the work", "yes", "go ahead", "Now edit files",
                     "Research the web " * 900 + " and publish a local report"):
            req = request()
            req["messages"].append({"role": "user", "content": text})
            self.assertIsNone(self.route(req))
        self.assertEqual(self.router.calls, [])

    def test_forced_choices_never_filter_or_make_a_jev_call(self):
        for choice in ({"type": "function", "function": {"name": "terminal"}},
                       {"type": "function", "name": "terminal"},
                       {"type": "tool", "name": "terminal"}, "required", "none", "terminal"):
            req = request()
            req["tool_choice"] = choice
            original = json.dumps(req)
            self.assertIsNone(self.route(req))
            self.assertEqual(json.dumps(req), original)
            self.assertEqual(self.mw.last_filter_reason, "explicit_tool_choice")
        self.assertEqual(self.router.calls, [])

    def test_host_prerequisites_remain_in_every_route_and_schema(self):
        required = ["skill_view", "skills_list", "skill_manage", "read_file", "write_file",
                    "search_files", "patch", "memory", "memory_search", "files_read", "skills_load"]
        for family, primary in (("web", "web_search"), ("apps", "mcp__service__get"),
                                ("terminal", "terminal"), ("media", "vision_analyze"),
                                ("github", "github_get_repo"), ("files", "read_file"),
                                ("memory", "memory"), ("skills", "skill_view")):
            for nested in (True, False):
                names = list(dict.fromkeys(required + [primary, "text_to_speech", "web_extract"]))
                tools = [{"type": "function", "function": {"name": n}} if nested else tool(n) for n in names]
                out, _, _ = filter_tools(tools, family)
                self.assertTrue(set(required).issubset({tool_name(t) for t in out}))

    def test_invalidation_wins_against_an_inflight_old_decision(self):
        entered, release = threading.Event(), threading.Event()
        original_decide = self.router.decide
        def slow(state, **kwargs):
            entered.set()
            self.assertTrue(release.wait(3))
            return original_decide(state, **kwargs)
        self.router.decide = slow
        results = []
        worker = threading.Thread(target=lambda: results.append(self.route(request())))
        worker.start()
        try:
            self.assertTrue(entered.wait(3))
            req = request()
            req["messages"].append({"role": "user", "content": []})
            self.assertIsNone(self.route(req))
        finally:
            release.set()
            worker.join(3)
        self.assertEqual(results, [None])
        self.assertIsNone(self.route(request()))
        self.assertEqual(len(self.router.calls), 1)

    def test_unexpected_router_exception_is_not_retried_in_same_turn(self):
        self.router.error = RuntimeError("synthetic failure")
        self.assertIsNone(self.route(request()))
        self.assertEqual(self.mw.last_filter_reason, "middleware_error")
        self.assertIsNone(self.route(request()))
        self.assertEqual(len(self.router.calls), 1)


class CompactionReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/private/tmp" if Path("/private/tmp").exists() else None)
        self.addCleanup(self.temp.cleanup)
        self.archive = OutputArchive(Path(self.temp.name) / "archive")
        self.config = CompactionConfig(mode="on", allow_external=True)

    def run_compact(self, rows, evaluator=None, **kwargs):
        return compactor(evaluator).compact(rows, config=kwargs.pop("config", self.config),
             model="typesafe/jev-1.13", timeout=2.5, archive=self.archive,
             session_id="synthetic-session", **kwargs)

    def test_external_compaction_requires_separate_opt_in_even_in_shadow(self):
        for mode in ("on", "shadow"):
            evaluator = Evaluator()
            out = self.run_compact(transcript(), evaluator, config=replace(self.config, mode=mode, allow_external=False))
            self.assertEqual(out.outcome, "external_not_approved")
            self.assertEqual(evaluator.calls, [])
            self.assertFalse(self.archive.root.exists())
        settings = read_compaction_config(FakeContext({"compaction_mode": "on"}))
        self.assertFalse(settings.allow_external)
        self.assertFalse(read_compaction_config(FakeContext({"compaction_allow_external": "true"})).allow_external)

    def test_matching_head_tail_does_not_hide_unique_middle_fact(self):
        rows = transcript()
        old = rows[4]["content"]
        rows[4]["content"] = old[:1000] + "CRITICAL_SHARD_COUNT=19" + old[1000:]
        evaluator = Evaluator()
        out = self.run_compact(rows, evaluator)
        self.assertEqual(out.outcome, "no_candidates")
        self.assertIs(out.messages, rows)
        self.assertEqual(evaluator.calls, [])

    def test_all_selected_duplicates_have_complete_retained_copy(self):
        rows = transcript(4)
        out = self.run_compact(rows)
        self.assertEqual(out.outcome, "applied")
        for candidate in candidates_for(rows, self.config):
            self.assertEqual(out.messages[candidate.retained_index]["content"], candidate.content)
            self.assertFalse(out.messages[candidate.retained_index]["content"].startswith(STUB_PREFIX))
        # Even outside the tail, the last exact copy cannot be archived.
        rows += [{"role": "user", "content": "A later exchange"}] + [{"role": "assistant", "content": "tail"}] * 6
        out = self.run_compact(rows)
        self.assertEqual(out.outcome, "applied")
        self.assertEqual(out.messages[14]["content"], rows[14]["content"])

    def test_same_content_from_a_different_tool_is_not_evidence_of_redundancy(self):
        rows = transcript()
        rows[7]["tool_calls"][0]["function"]["name"] = "web_extract"
        self.assertEqual(candidates_for(rows, self.config), [])

    def test_json_error_payloads_stay_verbatim_without_top_level_flag(self):
        for value in ({"error": "synthetic failure"}, {"ok": False}, {"success": False},
                      {"nested": {"status": "failed"}}, {"errors": ["unresolved"]}):
            rows = transcript()
            value["padding"] = "x" * 2000
            text = json.dumps(value)
            rows[4]["content"] = rows[8]["content"] = text
            self.assertEqual(candidates_for(rows, self.config), [])

    def test_memory_is_forwarded_and_sensitive_state_is_rejected_before_calls(self):
        evaluator = Evaluator()
        self.run_compact(transcript(), evaluator, memory_context="Keep the exact shard count.")
        self.assertIn("exact shard count", evaluator.calls[0]["state"]["memory"])
        evaluator = Evaluator()
        out = self.run_compact(transcript(), evaluator, memory_context="password is synthetic multiword value")
        self.assertEqual(out.outcome, "fallback_error")
        self.assertEqual(evaluator.calls, [])
        state = build_state(transcript(), self.config, memory_context='password="synthetic phrase"')
        self.assertNotIn("synthetic phrase", json.dumps(state))

    def test_partial_provider_failure_preserves_known_usage_without_claiming_total(self):
        evaluator = Evaluator()
        def partial(**kwargs):
            if evaluator.calls:
                raise RuntimeError("synthetic later-batch failure")
            return evaluator(**kwargs)
        rows = transcript(10)
        config = replace(self.config, max_request_tokens=3000, max_state_tokens=1500, preview_chars=100)
        out = self.run_compact(rows, partial, config=config)
        self.assertIs(out.messages, rows)
        self.assertEqual(out.outcome, "fallback_error")
        self.assertEqual(out.requests, 2)
        self.assertAlmostEqual(out.known_cost_usd, 0.00001)
        self.assertEqual(out.known_input_tokens, 10)
        self.assertIsNone(out.cost_usd)
        path = Path(self.temp.name) / "metrics.sqlite3"
        record_compaction(out.metadata(), path)
        summary = compaction_summary(path)
        self.assertAlmostEqual(summary["known_cost_usd"], out.known_cost_usd)
        self.assertIsNone(summary["cost_usd"])

    def test_cancelled_provider_response_cannot_write_archives(self):
        cancelled = False
        evaluator = Evaluator()
        def cancelling(**kwargs):
            nonlocal cancelled
            response = evaluator(**kwargs)
            cancelled = True
            return response
        rows = transcript()
        out = self.run_compact(rows, cancelling, should_abort=lambda: cancelled)
        self.assertEqual(out.outcome, "stale_attempt")
        self.assertIs(out.messages, rows)
        self.assertFalse(self.archive.root.exists())
        self.assertAlmostEqual(out.known_cost_usd, 0.00001)

    def test_failed_archive_batch_removes_only_new_raw_files(self):
        retained = self.archive.reference("synthetic-session")
        self.archive.write_batch([(retained, "retained exact output")])
        entries = [(self.archive.reference("synthetic-session"), "new output") for _ in range(2)]
        writer = self.archive._write_index
        calls = 0
        def fail_second(folder, record):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synthetic write failure")
            writer(folder, record)
        with mock.patch.object(self.archive, "_write_index", side_effect=fail_second):
            with self.assertRaises(OSError):
                self.archive.write_batch(entries)
        self.assertEqual(self.archive.recover(retained)["text"], "retained exact output")
        for ref, _ in entries:
            self.assertFalse((self.archive.root / ref.rsplit("/", 1)[0]).exists())

    def test_capacity_refuses_new_data_and_keeps_old_recovery(self):
        self.archive.max_bytes = 2500
        ref = self.archive.reference("synthetic-session")
        self.archive.write_batch([(ref, "x" * 1000)])
        with self.assertRaisesRegex(ValueError, "archive_capacity"):
            self.archive.write_batch([(self.archive.reference("synthetic-session"), "x" * 1000)])
        self.assertEqual(self.archive.recover(ref)["text"], "x" * 1000)

    def test_creation_syncs_each_new_ancestor_and_namespace_is_session_bound(self):
        self.archive.root = Path(self.temp.name) / "new-parent" / "archive"
        ref = self.archive.reference("synthetic-session")
        with mock.patch.object(self.archive, "_sync_directory", wraps=self.archive._sync_directory) as sync:
            self.archive.write_batch([(ref, "exact output")])
        synced = {c.args[0] for c in sync.call_args_list}
        self.assertIn(self.archive.root.parent.parent, synced)
        self.assertIn(self.archive.root.parent, synced)
        self.assertIn(self.archive.root, synced)
        self.assertTrue(OutputArchive.owns(ref, "synthetic-session"))
        self.assertFalse(OutputArchive.owns(ref, "other-session"))

    def test_cancellation_during_archive_batch_rolls_back_new_output(self):
        entries = [(self.archive.reference("synthetic-session"), "new exact output") for _ in range(2)]
        checks = iter((False, True))
        with self.assertRaises(InterruptedError):
            self.archive.write_batch(entries, should_abort=lambda: next(checks))
        self.assertEqual(list(self.archive.root.rglob("*.txt")), [])
        self.assertEqual(list(self.archive.root.rglob("INDEX.json")), [])


if __name__ == "__main__":
    unittest.main()
