import json
from pathlib import Path
import unittest

from jevperf.families import ROUTING_FAMILIES


FIXTURES = Path(__file__).parent / "fixtures" / "routing_cases.json"


class RoutingFixtureTests(unittest.TestCase):
    def test_fixture_corpus_covers_every_family(self):
        cases = json.loads(FIXTURES.read_text())
        self.assertEqual({case["family"] for case in cases}, set(ROUTING_FAMILIES))
        self.assertGreaterEqual(len(cases), 20)

    def test_fixture_ids_are_unique_and_content_is_nonempty(self):
        cases = json.loads(FIXTURES.read_text())
        ids = [case["id"] for case in cases]
        self.assertEqual(len(ids), len(set(ids)))
        for case in cases:
            self.assertTrue(case["prompt"].strip())
            self.assertIn(case["family"], ROUTING_FAMILIES)

    def test_mixed_fixtures_are_explicitly_multi(self):
        cases = json.loads(FIXTURES.read_text())
        mixed = [case for case in cases if case["id"].startswith("multi-")]
        self.assertGreaterEqual(len(mixed), 2)
        self.assertTrue(all(case["family"] == "multi" for case in mixed))


if __name__ == "__main__":
    unittest.main()
