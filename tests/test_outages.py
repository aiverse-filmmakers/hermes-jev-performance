import unittest

from jevperf.client import JevError
from jevperf.middleware import RoutingMiddleware
from jevperf.routing import JevRouter
from tests.fakes import FakeContext


class Credential:
    name = "OPENROUTER_JEV_API_TOKEN"
    token = "fixture-token"


def request():
    return {
        "model": "codex-model",
        "messages": [{"role": "user", "content": "search the web"}],
        "tools": [
            {"type": "function", "name": "web_search"},
            {"type": "function", "name": "terminal"},
        ],
    }


class OutageTests(unittest.TestCase):
    def router_for_error(self, error):
        def evaluator(**kwargs):
            raise error
        return JevRouter(
            evaluator=evaluator,
            credential_resolver=lambda: Credential(),
        )

    def call(self, router):
        middleware = RoutingMiddleware(
            FakeContext({"mode": "on"}),
            router=router,
        )
        result = middleware(
            request=request(),
            session_id="session",
            turn_id="turn",
            api_call_count=1,
            provider="openai-codex",
            model="codex-model",
            api_mode="codex_responses",
        )
        return middleware, result

    def test_timeout_fails_open(self):
        middleware, result = self.call(
            self.router_for_error(JevError("timeout", retryable=True))
        )
        self.assertIsNone(result)
        self.assertEqual(middleware.last_filter_reason, "jev_error")
        self.assertEqual(middleware.last_decision.error_category, "timeout")

    def test_rate_limit_fails_open(self):
        middleware, result = self.call(
            self.router_for_error(
                JevError("http", status_code=429, retryable=True)
            )
        )
        self.assertIsNone(result)
        self.assertEqual(middleware.last_filter_reason, "jev_error")
        self.assertEqual(middleware.last_decision.error_status_code, 429)

    def test_provider_500_fails_open(self):
        middleware, result = self.call(
            self.router_for_error(
                JevError("http", status_code=500, retryable=True)
            )
        )
        self.assertIsNone(result)
        self.assertEqual(middleware.last_filter_reason, "jev_error")
        self.assertEqual(middleware.last_decision.error_status_code, 500)

    def test_unexpected_provider_exception_fails_open(self):
        middleware, result = self.call(
            self.router_for_error(RuntimeError("synthetic provider failure"))
        )
        self.assertIsNone(result)
        self.assertEqual(middleware.last_filter_reason, "jev_error")
        self.assertEqual(middleware.last_decision.error_category, "request")


if __name__ == "__main__":
    unittest.main()
