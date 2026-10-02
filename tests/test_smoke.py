import unittest
from unittest import mock

from jevperf.credentials import Credential
from jevperf.smoke import run_smoke


class SmokeTests(unittest.TestCase):
    def test_missing_credential_makes_no_provider_call(self):
        with mock.patch(
            "jevperf.smoke.resolve_openrouter_credential",
            return_value=None,
        ), mock.patch("jevperf.smoke.evaluate") as evaluate:
            code, payload = run_smoke()
        self.assertEqual(code, 2)
        self.assertEqual(payload["error"], "missing_credential")
        evaluate.assert_not_called()

    def test_success_returns_safe_metadata_not_token(self):
        result = {
            "requested_model": "typesafe/jev-1.13",
            "model": "typesafe/jev-1.13-20260917",
            "answers": {
                "tool_family": {"choice": "web", "confidence": 0.95},
            },
            "latency_ms": 123.4,
            "usage": {"input_tokens": 10, "output_tokens": 2, "cost": 0.000001},
        }
        with mock.patch(
            "jevperf.smoke.resolve_openrouter_credential",
            return_value=Credential(
                name="OPENROUTER_JEV_API_TOKEN",
                token="SECRET_TOKEN_MUST_NOT_RETURN",
            ),
        ), mock.patch("jevperf.smoke.evaluate", return_value=result) as evaluate:
            code, payload = run_smoke()
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["choice"], "web")
        self.assertEqual(payload["credential_source"], "OPENROUTER_JEV_API_TOKEN")
        self.assertNotIn("SECRET_TOKEN_MUST_NOT_RETURN", repr(payload))
        self.assertEqual(
            evaluate.call_args.kwargs["token"],
            "SECRET_TOKEN_MUST_NOT_RETURN",
        )

    def test_safe_error_does_not_echo_token(self):
        with mock.patch(
            "jevperf.smoke.resolve_openrouter_credential",
            return_value=Credential(
                name="OPENROUTER_JEV_API_TOKEN",
                token="SECRET_TOKEN_MUST_NOT_RETURN",
            ),
        ), mock.patch(
            "jevperf.smoke.evaluate",
            side_effect=RuntimeError("provider exploded SECRET_TOKEN_MUST_NOT_RETURN"),
        ):
            code, payload = run_smoke()
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertNotIn("SECRET_TOKEN_MUST_NOT_RETURN", repr(payload))


if __name__ == "__main__":
    unittest.main()
