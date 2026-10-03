import threading
import time
import unittest

from jevperf.turns import (
    MAX_ROUTING_STATE_CHARS,
    TurnDecisionCache,
    extract_routing_state,
    redact_routing_state,
    turn_key,
)


class TurnTests(unittest.TestCase):
    def test_extracts_only_latest_user_message(self):
        request = {
            "messages": [
                {"role": "user", "content": "old request"},
                {"role": "assistant", "content": "old answer"},
                {"role": "user", "content": "latest request"},
            ]
        }
        self.assertEqual(extract_routing_state(request), "latest request")

    def test_extracts_responses_input_blocks(self):
        request = {
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "check"},
                        {"type": "input_text", "text": "the web"},
                    ],
                }
            ]
        }
        self.assertEqual(extract_routing_state(request), "check\nthe web")

    def test_redacts_common_secret_shapes(self):
        fake_openai_token = "sk-" + "abcdefghijklmnopqrstuvwxyz"
        text = (
            "Authorization Bearer abcdefghijklmnop "
            "api_key=supersecretvalue "
            "password: anothersecret "
            + fake_openai_token
        )
        redacted = redact_routing_state(text)
        self.assertNotIn("abcdefghijklmnop", redacted)
        self.assertNotIn("supersecretvalue", redacted)
        self.assertNotIn("anothersecret", redacted)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", redacted)

    def test_state_is_bounded(self):
        state = extract_routing_state({
            "messages": [{"role": "user", "content": "x" * (MAX_ROUTING_STATE_CHARS + 100)}]
        })
        self.assertEqual(len(state), MAX_ROUTING_STATE_CHARS)

    def test_missing_user_state_fails_open(self):
        self.assertIsNone(extract_routing_state({"messages": [{"role": "assistant", "content": "hi"}]}))

    def test_turn_key_is_opaque_and_stable(self):
        key = turn_key("sensitive-session-id", "sensitive-turn-id")
        self.assertIsNotNone(key)
        self.assertEqual(len(key), 32)
        self.assertNotIn("sensitive", key)
        self.assertEqual(key, turn_key("sensitive-session-id", "sensitive-turn-id"))
        self.assertNotEqual(key, turn_key("sensitive-session-id", "other-turn"))
        self.assertIsNone(turn_key("s", ""))

    def test_cache_is_bounded_and_does_not_store_state(self):
        cache = TurnDecisionCache(max_entries=2)
        cache.put("a", {"family": "web"})
        cache.put("b", {"family": "files"})
        cache.put("c", {"family": "memory"})
        self.assertEqual(len(cache), 2)
        self.assertIsNone(cache.get("a"))
        self.assertEqual(cache.get("c"), {"family": "memory"})

    def test_get_or_compute_runs_factory_once_per_turn_under_concurrency(self):
        cache = TurnDecisionCache()
        calls = []
        results = []
        barrier = threading.Barrier(4)

        def factory():
            calls.append(1)
            time.sleep(0.03)
            return {"family": "web"}

        def worker():
            barrier.wait()
            results.append(cache.get_or_compute("opaque-turn", factory))

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(len(calls), 1)
        self.assertEqual(results, [{"family": "web"}] * 4)


if __name__ == "__main__":
    unittest.main()
