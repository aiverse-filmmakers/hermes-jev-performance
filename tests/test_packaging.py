import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_native_hermes_package_layout_is_complete(self):
        required = [
            ROOT / "plugin.yaml",
            ROOT / "__init__.py",
            ROOT / "after-install.md",
            ROOT / "dashboard" / "manifest.json",
            ROOT / "dashboard" / "plugin_api.py",
            ROOT / "dashboard" / "dist" / "index.js",
            ROOT / "dashboard" / "dist" / "style.css",
            ROOT / "docs" / "INSTALL.md",
        ]
        self.assertEqual([str(p) for p in required if not p.is_file()], [])

    def test_manifest_declares_hermes_floor_and_no_runtime_dependencies(self):
        text = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
        self.assertRegex(text, r'(?m)^requires_hermes:\s*["\x27]>=0\.21\.5["\x27]')
        self.assertNotIn("pip_dependencies:", text)
        self.assertNotIn("python_dependencies:", text)

    def test_dashboard_and_plugin_versions_match(self):
        plugin_text = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
        match = re.search(r'(?m)^version:\s*["\x27]?([^\s"\x27]+)', plugin_text)
        self.assertIsNotNone(match)
        dashboard = json.loads(
            (ROOT / "dashboard" / "manifest.json").read_text(encoding="utf-8")
        )
        from jevperf import __version__
        self.assertEqual(match.group(1), __version__)
        self.assertEqual(dashboard["version"], __version__)

    def test_install_doc_uses_native_hermes_lifecycle(self):
        text = (ROOT / "docs" / "INSTALL.md").read_text(encoding="utf-8")
        for command in (
            "hermes plugins install",
            "hermes plugins update",
            "hermes plugins disable",
            "hermes plugins remove",
            "hermes plugins doctor",
        ):
            self.assertIn(command, text)
        self.assertNotIn("curl |", text)
        self.assertNotIn("wget |", text)


if __name__ == "__main__":
    unittest.main()
