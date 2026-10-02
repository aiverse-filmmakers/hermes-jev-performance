import io
import json
import unittest
import urllib.error
from unittest import mock

from jevperf import client


CHOICE = {
    "tool_family": {
        "type": "choice",
        "instructions": "Choose the best tool family.",
        "criteria": {
            "web": "Public web research.",
            "none": "No tool.",
        },
    }
}

RESPONSE = {
    "model": "typesafe/jev-1.13-20260917",
    "answers": {
        "tool_family": {
            "type": "choice",
            "choice": "web",
            "confidence": 0.94,
            "probabilities": {"web": 0.94, "none": 0.06},
        }
    },
    "usage": {
        "input_tokens": 288,
        "output_tokens": 23,
        "cost": 0.000012096,
        "ignored_extension": "do not retain",
    },
}


class ClientTests(unittest.TestCase):
    def evaluate(self, **changes):
        args = {
            "token": "fixture-token",
            "state": "Search the web.",
            "questions": CHOICE,
        }
        args.update(changes)
        return client.evaluate(**args)

    def test_endpoint_payload_default_model_and_usage(self):
        seen = {}

        def fake_transport(url, token, body, timeout):
            seen.update({
                "url": url,
                "token": token,
                "payload": json.loads(body),
                "timeout": timeout,
            })
            return json.dumps(RESPONSE).encode()

        with mock.patch.object(client, "_transport", side_effect=fake_transport):
            result = self.evaluate()

        self.assertEqual(seen["url"], client.OPENROUTER_DECISIONS_URL)
        self.assertEqual(seen["payload"]["model"], "typesafe/jev-1.13")
        self.assertEqual(result["requested_model"], "typesafe/jev-1.13")
        self.assertEqual(result["model"], RESPONSE["model"])
        self.assertEqual(result["answers"]["tool_family"]["choice"], "web")
        self.assertEqual(result["usage"]["cost"], 0.000012096)
        self.assertNotIn("ignored_extension", result["usage"])
        self.assertGreaterEqual(result["latency_ms"], 0)

    def test_latest_alias_can_be_selected_explicitly(self):
        seen = {}

        def fake_transport(_url, _token, body, _timeout):
            seen["model"] = json.loads(body)["model"]
            return json.dumps(RESPONSE).encode()

        with mock.patch.object(client, "_transport", side_effect=fake_transport):
            self.evaluate(model="~typesafe/jev-latest")
        self.assertEqual(seen["model"], "~typesafe/jev-latest")

    def test_missing_usage_is_allowed(self):
        response = {key: value for key, value in RESPONSE.items() if key != "usage"}
        with mock.patch.object(
            client,
            "_transport",
            return_value=json.dumps(response).encode(),
        ):
            result = self.evaluate()
        self.assertEqual(result["usage"], {})

    def test_missing_cost_is_allowed(self):
        response = json.loads(json.dumps(RESPONSE))
        response["usage"].pop("cost")
        with mock.patch.object(
            client,
            "_transport",
            return_value=json.dumps(response).encode(),
        ):
            result = self.evaluate()
        self.assertNotIn("cost", result["usage"])
        self.assertEqual(result["usage"]["input_tokens"], 288)

    def test_malformed_json_is_safe_error(self):
        with mock.patch.object(client, "_transport", return_value=b"{not-json"):
            with self.assertRaises(client.JevError) as raised:
                self.evaluate()
        self.assertEqual(raised.exception.category, "invalid_json")

    def test_missing_answer_is_rejected(self):
        response = {**RESPONSE, "answers": {}}
        with mock.patch.object(
            client,
            "_transport",
            return_value=json.dumps(response).encode(),
        ):
            with self.assertRaises(client.JevError) as raised:
                self.evaluate()
        self.assertEqual(raised.exception.category, "invalid_response")

    def test_invalid_choice_is_rejected(self):
        response = json.loads(json.dumps(RESPONSE))
        response["answers"]["tool_family"]["choice"] = "terminal"
        with mock.patch.object(
            client,
            "_transport",
            return_value=json.dumps(response).encode(),
        ):
            with self.assertRaises(client.JevError):
                self.evaluate()

    def test_timeout_is_not_retried(self):
        calls = 0

        def fail(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            raise client.JevError("timeout", retryable=True)

        with mock.patch.object(client, "_transport", side_effect=fail):
            with self.assertRaises(client.JevError) as raised:
                self.evaluate()
        self.assertEqual(calls, 1)
        self.assertEqual(raised.exception.category, "timeout")
        self.assertTrue(raised.exception.retryable)

    def test_question_validation(self):
        with self.assertRaises(client.JevError):
            self.evaluate(questions={
                "tool_family": {
                    "type": "choice",
                    "instructions": "Choose.",
                    "criteria": {"only": "one"},
                }
            })

    def test_payload_size_limit(self):
        with self.assertRaises(client.JevError) as raised:
            self.evaluate(state="x" * (client.MAX_PAYLOAD_BYTES + 1))
        self.assertEqual(raised.exception.category, "payload_too_large")

    def test_safe_error_details_never_echo_raw_exception(self):
        error = client.JevError("http", status_code=401)
        details = client.safe_error_details(error)
        self.assertEqual(details["status_code"], 401)
        self.assertEqual(details["category"], "http")
        self.assertNotIn("fixture-token", str(details))


class TransportTests(unittest.TestCase):
    class FakeHeaders(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    class FakeResponse:
        def __init__(self, raw, headers=None):
            self.raw = raw
            self.headers = TransportTests.FakeHeaders(headers or {})

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, amount):
            return self.raw[:amount]

    class FakeOpener:
        def __init__(self, result):
            self.result = result
            self.seen = None

        def open(self, request, timeout):
            self.seen = (request, timeout)
            if isinstance(self.result, Exception):
                raise self.result
            return self.result

    def test_http_status_mapping(self):
        for status, retryable in ((400, False), (401, False), (402, False), (429, True), (500, True)):
            with self.subTest(status=status):
                error = urllib.error.HTTPError(
                    client.OPENROUTER_DECISIONS_URL,
                    status,
                    "fixture",
                    {},
                    io.BytesIO(b"provider body must not be exposed"),
                )
                opener = self.FakeOpener(error)
                with mock.patch.object(
                    client.urllib.request,
                    "build_opener",
                    return_value=opener,
                ):
                    with self.assertRaises(client.JevError) as raised:
                        client._transport(
                            client.OPENROUTER_DECISIONS_URL,
                            "fixture-token",
                            b"{}",
                            1.0,
                        )
                self.assertEqual(raised.exception.status_code, status)
                self.assertEqual(raised.exception.retryable, retryable)
                self.assertNotIn("provider body", str(raised.exception))

    def test_response_size_limit(self):
        opener = self.FakeOpener(
            self.FakeResponse(
                b"{}",
                {"Content-Length": str(client.MAX_RESPONSE_BYTES + 1)},
            )
        )
        with mock.patch.object(
            client.urllib.request,
            "build_opener",
            return_value=opener,
        ):
            with self.assertRaises(client.JevError) as raised:
                client._transport(
                    client.OPENROUTER_DECISIONS_URL,
                    "fixture-token",
                    b"{}",
                    1.0,
                )
        self.assertEqual(raised.exception.category, "response_too_large")


if __name__ == "__main__":
    unittest.main()
