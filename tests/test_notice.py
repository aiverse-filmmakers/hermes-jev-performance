import unittest

from jevperf.notice import build_notice_hook
from jevperf.routing import RoutingDecision
from tests.fakes import FakeContext


class FakeRouterMiddleware:
    def __init__(self, latest=None):
        self.latest = latest

    def latest_for_session(self, session_id):
        return self.latest


class NoticeTests(unittest.TestCase):
    def decision(self):
        return RoutingDecision(
            family="web",
            confidence=0.94,
            accepted=True,
            reason="accepted",
            latency_ms=321.4,
        )

    def test_notice_is_off_by_default(self):
        hook = build_notice_hook(
            FakeContext(),
            FakeRouterMiddleware((self.decision(), "on", "filtered")),
        )
        self.assertIsNone(hook(response_text="Answer", session_id="session"))

    def test_notice_appends_compact_on_mode_footer(self):
        hook = build_notice_hook(
            FakeContext({"notice": True, "mode": "on"}),
            FakeRouterMiddleware((self.decision(), "on", "filtered")),
        )
        result = hook(response_text="Answer", session_id="session")
        self.assertEqual(result, "Answer\n\n[Jev] web · 94% · 321ms")

    def test_shadow_notice_is_labeled(self):
        hook = build_notice_hook(
            FakeContext({"notice": True, "mode": "shadow"}),
            FakeRouterMiddleware((self.decision(), "shadow", "shadow")),
        )
        result = hook(response_text="Answer", session_id="session")
        self.assertIn("[Jev shadow] web", result)

    def test_off_mode_never_appends_stale_notice(self):
        hook = build_notice_hook(
            FakeContext({"notice": True, "mode": "off"}),
            FakeRouterMiddleware((self.decision(), "on", "filtered")),
        )
        self.assertIsNone(hook(response_text="Answer", session_id="session"))

    def test_missing_session_decision_fails_open(self):
        hook = build_notice_hook(
            FakeContext({"notice": True, "mode": "on"}),
            FakeRouterMiddleware(None),
        )
        self.assertIsNone(hook(response_text="Answer", session_id="session"))


if __name__ == "__main__":
    unittest.main()
