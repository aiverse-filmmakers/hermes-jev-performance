import unittest

from jevperf.middleware import RoutingMiddleware
from jevperf.routing import RoutingDecision
from tests.fakes import FakeContext


def tool(name):
    return {"type": "function", "name": name, "description": name}


def request():
    return {
        "model": "codex-model",
        "extra_headers": {"x-test": "keep"},
        "messages": [{"role": "user", "content": "search the web"}],
        "tools": [
            tool("web_search"),
            tool("terminal"),
            tool("read_file"),
            tool("tool_call"),
            tool("clarify"),
            tool("custom_future_tool"),
        ],
    }


class FakeRouter:
    def __init__(self, decision=None, error=None):
        self.decision = decision
        self.error = error
        self.calls = []

    def decide(self, state, **kwargs):
        self.calls.append((state, kwargs))
        if self.error is not None:
            raise self.error
        return self.decision


class MiddlewareTests(unittest.TestCase):
    def decision(self, family="web", confidence=0.95, accepted=True, reason="accepted"):
        return RoutingDecision(
            family=family,
            confidence=confidence,
            accepted=accepted,
            reason=reason,
            requested_model="typesafe/jev-1.13",
            actual_model="typesafe/jev-1.13",
            latency_ms=10,
        )

    def call(self, middleware, req=None, **extra):
        return middleware(
            request=req or request(),
            session_id=extra.pop("session_id", "session"),
            turn_id=extra.pop("turn_id", "turn"),
            api_call_count=extra.pop("api_call_count", 1),
            provider="openai-codex",
            model="codex-model",
            api_mode="codex_responses",
            **extra,
        )

    def test_off_mode_makes_zero_jev_calls(self):
        router = FakeRouter(self.decision())
        mw = RoutingMiddleware(FakeContext({"mode": "off"}), router=router)
        self.assertIsNone(self.call(mw))
        self.assertEqual(router.calls, [])
        self.assertEqual(mw.last_filter_reason, "mode_off")

    def test_shadow_calls_once_but_never_changes_request(self):
        router = FakeRouter(self.decision())
        mw = RoutingMiddleware(FakeContext({"mode": "shadow"}), router=router)
        self.assertIsNone(self.call(mw, api_call_count=1))
        self.assertIsNone(self.call(mw, api_call_count=2))
        self.assertEqual(len(router.calls), 1)
        self.assertEqual(mw.last_filter_reason, "shadow")

    def test_on_filters_known_competing_tools(self):
        router = FakeRouter(self.decision("web"))
        mw = RoutingMiddleware(FakeContext({"mode": "on"}), router=router)
        original = request()
        result = self.call(mw, req=original)
        self.assertIsNotNone(result)
        updated = result["request"]
        names = [item["name"] for item in updated["tools"]]
        self.assertEqual(
            names,
            ["web_search", "clarify", "custom_future_tool"],
        )
        self.assertEqual(updated["model"], original["model"])
        self.assertEqual(updated["extra_headers"], original["extra_headers"])
        self.assertEqual(original["tools"][1]["name"], "terminal")
        self.assertEqual(result["source"], "hermes-jev-performance")

    def test_tool_loop_reuses_same_turn_decision(self):
        router = FakeRouter(self.decision("web"))
        mw = RoutingMiddleware(FakeContext({"mode": "on"}), router=router)
        first = self.call(mw, api_call_count=1)
        second = self.call(mw, api_call_count=2)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(len(router.calls), 1)

    def test_new_turn_gets_new_decision(self):
        router = FakeRouter(self.decision("web"))
        mw = RoutingMiddleware(FakeContext({"mode": "on"}), router=router)
        self.call(mw, turn_id="turn-1")
        self.call(mw, turn_id="turn-2")
        self.assertEqual(len(router.calls), 2)

    def test_multi_never_filters(self):
        router = FakeRouter(self.decision("multi"))
        mw = RoutingMiddleware(FakeContext({"mode": "on"}), router=router)
        self.assertIsNone(self.call(mw))
        self.assertEqual(mw.last_filter_reason, "unrestricted_multi")

    def test_low_confidence_never_filters(self):
        router = FakeRouter(self.decision("web", 0.4, False, "low_or_missing_confidence"))
        mw = RoutingMiddleware(FakeContext({"mode": "on"}), router=router)
        self.assertIsNone(self.call(mw))
        self.assertEqual(mw.last_filter_reason, "low_or_missing_confidence")

    def test_missing_turn_id_fails_open_without_jev_call(self):
        router = FakeRouter(self.decision())
        mw = RoutingMiddleware(FakeContext({"mode": "on"}), router=router)
        self.assertIsNone(self.call(mw, turn_id=""))
        self.assertEqual(router.calls, [])
        self.assertEqual(mw.last_filter_reason, "missing_turn_id")

    def test_missing_user_state_fails_open(self):
        router = FakeRouter(self.decision())
        mw = RoutingMiddleware(FakeContext({"mode": "on"}), router=router)
        req = {"tools": [tool("web_search")], "messages": [{"role": "assistant", "content": "hi"}]}
        self.assertIsNone(self.call(mw, req=req))
        self.assertEqual(router.calls, [])
        self.assertEqual(mw.last_filter_reason, "missing_user_state")

    def test_router_exception_fails_open(self):
        router = FakeRouter(error=RuntimeError("boom"))
        mw = RoutingMiddleware(FakeContext({"mode": "on"}), router=router)
        self.assertIsNone(self.call(mw))
        self.assertEqual(mw.last_filter_reason, "middleware_error")

    def test_zero_matching_family_tools_fails_open(self):
        router = FakeRouter(self.decision("memory"))
        mw = RoutingMiddleware(FakeContext({"mode": "on"}), router=router)
        self.assertIsNone(self.call(mw))
        self.assertEqual(mw.last_filter_reason, "no_family_tools")


if __name__ == "__main__":
    unittest.main()
