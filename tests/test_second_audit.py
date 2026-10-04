"""Independent behavioral regressions from the second Hermes audit."""
from dataclasses import replace
import fcntl
import json
import threading
import time
import unittest
from unittest import mock

from jevperf.compaction import candidates_for
from jevperf.turns import safe_external_text
from tests import test_review_regressions as fixtures
from tests.test_middleware import request
from tests.test_compaction import transcript, Evaluator


class RoutingSecondAuditTests(unittest.TestCase):
    setUp = fixtures.RoutingReviewTests.setUp
    route = fixtures.RoutingReviewTests.route

    def test_secret_concatenations_and_unquoted_multiword_values_make_no_calls(self):
        cases = ('password="SYNTHETIC_HEAD"SYNTHETIC_TAIL',
                 "OPENROUTER_API_KEY='SYNTHETIC_HEAD'SYNTHETIC_TAIL",
                 'api_key="SYNTHETIC_HEAD"\'SYNTHETIC_TAIL\'',
                 'api_key=SYNTHETIC_HEAD"SYNTHETIC_TAIL"',
                 'client_secret="SYNTHETIC_HEAD"${SYNTHETIC_TAIL}',
                 'client_secret=synthetic first second')
        for mode in ('on', 'shadow'):
            self.ctx.settings['mode'] = mode
            for text in cases:
                with self.subTest(mode=mode, text=text):
                    self.assertIsNone(safe_external_text(text))
                    req = request()
                    req['messages'][-1]['content'] = text
                    self.assertIsNone(self.route(req))
        self.assertEqual(self.router.calls, [])

    def test_contextual_polite_followups_keep_all_tools_without_history(self):
        for text in ('Please continue with the work we discussed earlier.',
                     'Do the same thing as last time',
                     'Okay, please finish everything we agreed earlier.',
                     'Use the previous instructions to complete the remaining work.'):
            with self.subTest(text=text):
                req = request()
                req['messages'].append({'role': 'user', 'content': text})
                self.assertIsNone(self.route(req))
        self.assertEqual(self.router.calls, [])

    def test_off_revokes_inflight_route_and_on_does_not_revive_it(self):
        entered, release = threading.Event(), threading.Event()
        original = self.router.decide
        def slow(state, **kwargs):
            entered.set()
            if not release.wait(3):
                raise RuntimeError('test worker timeout')
            return original(state, **kwargs)
        self.router.decide = slow
        out = []
        worker = threading.Thread(target=lambda: out.append(self.route(request())))
        worker.start()
        try:
            self.assertTrue(entered.wait(3))
            self.ctx.settings['mode'] = 'off'
            self.assertIsNone(self.route(request()))
            # Revocation cannot disappear when another turn evicts the cache row.
            self.cache.max_entries = 1
            self.cache.put('another-turn', (None, None))
            self.ctx.settings['mode'] = 'on'
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(out, [None])
        self.assertIsNone(self.route(request()))
        self.assertEqual(len(self.router.calls), 1)
        self.assertIsNotNone(self.mw(request=request(), session_id='synthetic-session', turn_id='new-turn'))
        self.assertEqual(len(self.router.calls), 2)


class CompactionSecondAuditTests(unittest.TestCase):
    setUp = fixtures.CompactionReviewTests.setUp
    run_compact = fixtures.CompactionReviewTests.run_compact

    def test_secret_boundary_check_covers_state_memory_and_output_in_shadow_and_on(self):
        for mode in ('shadow', 'on'):
            for location in ('memory', 'user', 'tool'):
                with self.subTest(mode=mode, location=location):
                    rows = transcript()
                    text = 'client_secret=synthetic first second'
                    kwargs = {'memory_context': text} if location == 'memory' else {}
                    if location == 'user':
                        rows[1]['content'] = text
                    if location == 'tool':
                        rows[4]['content'] = text + '\n' + 'x' * 3000
                    evaluator = Evaluator()
                    out = self.run_compact(rows, evaluator, config=replace(self.config, mode=mode), **kwargs)
                    self.assertEqual(out.outcome, 'fallback_error')
                    self.assertIs(out.messages, rows)
                    self.assertEqual(evaluator.calls, [])
        self.assertFalse(self.archive.root.exists())

    def test_exit_code_and_stderr_errors_are_never_assessed(self):
        for value in ({'exit_code': 1}, {'returncode': 2}, {'exit_status': '1'},
                      {'nested': {'return_code': -1}}, {'stderr': 'unresolved failure'}):
            with self.subTest(value=value):
                rows = transcript()
                rows[4]['content'] = json.dumps({**value, 'padding': 'x' * 3000})
                self.assertEqual(candidates_for(rows, self.config), [])
                evaluator = Evaluator()
                self.assertEqual(self.run_compact(rows, evaluator).outcome, 'no_candidates')
                self.assertEqual(evaluator.calls, [])

    def test_archive_lock_wait_respects_attempt_deadline(self):
        retained = self.archive.reference('synthetic-session')
        self.archive.write_batch([(retained, 'retained output')])
        with (self.archive.root / 'LOCK').open('rb') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            # Bound the test itself if an implementation regresses to blocking flock.
            release = threading.Timer(0.7, lambda: fcntl.flock(lock, fcntl.LOCK_UN))
            release.start()
            try:
                started = time.monotonic()
                rows = transcript()
                out = self.run_compact(rows, config=replace(self.config, deadline_seconds=0.2))
                elapsed = time.monotonic() - started
            finally:
                release.cancel()
                release.join()
        self.assertEqual(out.outcome, 'deadline')
        self.assertIs(out.messages, rows)
        self.assertLess(elapsed, 0.5)
        self.assertEqual(self.archive.recover(retained)['text'], 'retained output')
        self.assertEqual(len(list(self.archive.root.rglob('*.txt'))), 1)

    def test_cancel_after_durable_batch_removes_only_new_archives(self):
        retained = self.archive.reference('synthetic-session')
        self.archive.write_batch([(retained, 'retained output')])
        cancelled = False
        write = self.archive.write_batch
        def cancel_after_write(*args, **kwargs):
            nonlocal cancelled
            write(*args, **kwargs)
            cancelled = True
        rows = transcript()
        with mock.patch.object(self.archive, 'write_batch', side_effect=cancel_after_write):
            out = self.run_compact(rows, should_abort=lambda: cancelled)
        self.assertEqual(out.outcome, 'stale_attempt')
        self.assertIs(out.messages, rows)
        self.assertEqual(out.archive_references, [])
        self.assertEqual(out.estimated_tokens_after, out.estimated_tokens_before)
        self.assertEqual(self.archive.recover(retained)['text'], 'retained output')
        self.assertEqual(len(list(self.archive.root.rglob('*.txt'))), 1)
        self.assertNotIn('archive_references', out.metadata())
