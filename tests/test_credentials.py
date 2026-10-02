import os
import unittest
from unittest import mock

from jevperf.credentials import (
    DEDICATED_OPENROUTER_SECRET,
    GENERIC_OPENROUTER_SECRET,
    resolve_openrouter_credential,
)


class CredentialTests(unittest.TestCase):
    def test_dedicated_key_wins(self):
        values = {
            DEDICATED_OPENROUTER_SECRET: "dedicated",
            GENERIC_OPENROUTER_SECRET: "generic",
        }
        credential = resolve_openrouter_credential(values.get)
        self.assertEqual(credential.name, DEDICATED_OPENROUTER_SECRET)
        self.assertEqual(credential.token, "dedicated")
        self.assertNotIn("dedicated", repr(credential))

    def test_generic_key_is_compatibility_fallback(self):
        values = {
            DEDICATED_OPENROUTER_SECRET: "",
            GENERIC_OPENROUTER_SECRET: "generic",
        }
        credential = resolve_openrouter_credential(values.get)
        self.assertEqual(credential.name, GENERIC_OPENROUTER_SECRET)
        self.assertEqual(credential.token, "generic")

    def test_missing_keys_returns_none(self):
        self.assertIsNone(resolve_openrouter_credential(lambda _name: ""))

    def test_environment_fallback_outside_hermes(self):
        with mock.patch.dict(os.environ, {
            DEDICATED_OPENROUTER_SECRET: "fixture",
        }, clear=True):
            credential = resolve_openrouter_credential()
        self.assertEqual(credential.name, DEDICATED_OPENROUTER_SECRET)
        self.assertEqual(credential.token, "fixture")


if __name__ == "__main__":
    unittest.main()
