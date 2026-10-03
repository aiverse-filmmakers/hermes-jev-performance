import json
import pathlib
import unittest

from jevperf import __version__


ROOT = pathlib.Path(__file__).resolve().parents[1]


class DashboardAssetTests(unittest.TestCase):
    def test_manifest_matches_runtime_contract(self):
        manifest = json.loads(
            (ROOT / "dashboard" / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["name"], "hermes-jev-performance")
        self.assertEqual(manifest["version"], __version__)
        self.assertEqual(manifest["tab"]["path"], "/jev-performance")
        self.assertEqual(manifest["tab"]["position"], "after:analytics")
        self.assertEqual(manifest["entry"], "dist/index.js")
        self.assertEqual(manifest["css"], "dist/style.css")
        self.assertEqual(manifest["api"], "plugin_api.py")

    def test_bundle_uses_hermes_sdk_and_authenticated_fetch_helper(self):
        source = (ROOT / "dashboard" / "dist" / "index.js").read_text(encoding="utf-8")
        self.assertIn("window.__HERMES_PLUGIN_SDK__", source)
        self.assertIn('registry.register("hermes-jev-performance"', source)
        self.assertIn("SDK.fetchJSON", source)
        self.assertNotIn("window.__HERMES_SESSION_TOKEN__", source)
        self.assertNotIn("localStorage", source)

    def test_bundle_explicitly_propagates_management_profile(self):
        source = (ROOT / "dashboard" / "dist" / "index.js").read_text(encoding="utf-8")
        self.assertIn('new URLSearchParams(window.location.search).get("profile")', source)
        self.assertIn('SDK.fetchJSON(apiUrl("/status"))', source)
        self.assertIn('SDK.fetchJSON(apiUrl("/mode"), {', source)
        self.assertIn('profile=" + encodeURIComponent(profile)', source)

    def test_bundle_exposes_required_latency_and_cost_metrics(self):
        source = (ROOT / "dashboard" / "dist" / "index.js").read_text(encoding="utf-8")
        self.assertIn("Jev latency p50 / p95", source)
        self.assertIn("summary.p50_jev_latency_ms", source)
        self.assertIn("summary.p95_jev_latency_ms", source)
        self.assertIn("Jev cost avg / total", source)
        self.assertIn("summary.avg_jev_cost_usd", source)
        self.assertIn("summary.total_jev_cost_usd", source)

    def test_backend_declares_bounded_status_summary_and_mode_routes(self):
        source = (ROOT / "dashboard" / "plugin_api.py").read_text(encoding="utf-8")
        self.assertIn('@router.get("/status")', source)
        self.assertIn('@router.get("/summary")', source)
        self.assertIn('@router.put("/mode")', source)
        self.assertIn("ge=1", source)
        self.assertIn("le=24 * 3650", source)
        self.assertNotIn("user_message", source)
        self.assertNotIn("conversation_history", source)


if __name__ == "__main__":
    unittest.main()
