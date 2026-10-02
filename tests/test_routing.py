import unittest

from jevperf.client import JevError
from jevperf.credentials import Credential
from jevperf.routing import JevRouter


class RoutingTests(unittest.TestCase):
    def router(self, response=None, error=None, credential=True):
        def resolver():
            return Credential("OPENROUTER_JEV_API_TOKEN", "fixture") if credential else None

        def evaluator(**kwargs):
            if error is not None:
                raise error
            return response

        return JevRouter(evaluator=evaluator, credential_resolver=resolver)

    def test_accepts_confident_route_and_preserves_metrics(self):
        router = self.router({
            "model": "typesafe/jev-1.13-20260917",
            "requested_model": "typesafe/jev-1.13",
            "answers": {
                "tool_family": {
                    "type": "choice",
                    "choice": "web",
                    "confidence": 0.94,
                }
            },
            "usage": {
                "input_tokens": 100,
                "output_tokens": 10,
                "cost": 0.00001,
            },
            "latency_ms": 321.5,
        })
        result = router.decide(
            "search the web",
            provider="openrouter",
            model="typesafe/jev-1.13",
            timeout_seconds=2.5,
            min_confidence=0.70,
        )
        self.assertTrue(result.accepted)
        self.assertTrue(result.can_filter)
        self.assertEqual(result.family, "web")
        self.assertEqual(result.confidence, 0.94)
        self.assertEqual(result.actual_model, "typesafe/jev-1.13-20260917")
        self.assertEqual(result.latency_ms, 321.5)
        self.assertEqual(result.cost_usd, 0.00001)

    def test_low_confidence_is_not_applyable(self):
        router = self.router({
            "model": "typesafe/jev-1.13",
            "requested_model": "typesafe/jev-1.13",
            "answers": {"tool_family": {"type": "choice", "choice": "web", "confidence": 0.4}},
            "usage": {},
            "latency_ms": 10,
        })
        result = router.decide(
            "ambiguous",
            provider="openrouter",
            model="typesafe/jev-1.13",
            timeout_seconds=2.5,
            min_confidence=0.70,
        )
        self.assertFalse(result.accepted)
        self.assertFalse(result.can_filter)
        self.assertEqual(result.reason, "low_or_missing_confidence")

    def test_multi_is_valid_but_never_filters(self):
        router = self.router({
            "model": "typesafe/jev-1.13",
            "requested_model": "typesafe/jev-1.13",
            "answers": {"tool_family": {"type": "choice", "choice": "multi", "confidence": 0.99}},
            "usage": {},
            "latency_ms": 10,
        })
        result = router.decide(
            "research online then save a local report",
            provider="openrouter",
            model="typesafe/jev-1.13",
            timeout_seconds=2.5,
            min_confidence=0.70,
        )
        self.assertTrue(result.accepted)
        self.assertFalse(result.can_filter)
        self.assertEqual(result.family, "multi")

    def test_missing_credential_fails_open_without_evaluation(self):
        calls = []
        router = JevRouter(
            evaluator=lambda **kwargs: calls.append(kwargs),
            credential_resolver=lambda: None,
        )
        result = router.decide(
            "search",
            provider="openrouter",
            model="typesafe/jev-1.13",
            timeout_seconds=2.5,
            min_confidence=0.70,
        )
        self.assertEqual(calls, [])
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "missing_credential")

    def test_jev_error_becomes_safe_fallback(self):
        router = self.router(error=JevError("http", status_code=429, retryable=True))
        result = router.decide(
            "search",
            provider="openrouter",
            model="typesafe/jev-1.13",
            timeout_seconds=2.5,
            min_confidence=0.70,
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "jev_error")
        self.assertEqual(result.error_category, "http")
        self.assertEqual(result.error_status_code, 429)

    def test_unsupported_provider_never_reads_credentials(self):
        calls = []
        router = JevRouter(
            evaluator=lambda **kwargs: None,
            credential_resolver=lambda: calls.append("credential"),
        )
        result = router.decide(
            "search",
            provider="other",
            model="model",
            timeout_seconds=2.5,
            min_confidence=0.70,
        )
        self.assertEqual(calls, [])
        self.assertEqual(result.reason, "unsupported_provider")


if __name__ == "__main__":
    unittest.main()
