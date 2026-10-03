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
            ROOT / "agent" / "plugin.yaml",
            ROOT / "agent" / "__init__.py",
            ROOT / "agent" / "jevperf" / "plugin.py",
            ROOT / "agent" / "dashboard" / "manifest.json",
            ROOT / "agent" / "dashboard" / "plugin_api.py",
            ROOT / "agent" / "dashboard" / "server-only.js",
            ROOT / "desktop" / "plugin.js",
            ROOT / "desktop" / "README.md",
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
        agent_manifest = re.search(
            r'(?m)^version:\s*["\x27]?([^\s"\x27]+)',
            (ROOT / "agent" / "plugin.yaml").read_text(encoding="utf-8"),
        )
        server_dashboard = json.loads(
            (ROOT / "agent" / "dashboard" / "manifest.json").read_text(encoding="utf-8")
        )
        from jevperf import __version__
        self.assertEqual(match.group(1), __version__)
        self.assertEqual(agent_manifest.group(1), __version__)
        self.assertEqual(dashboard["version"], __version__)
        self.assertEqual(server_dashboard["version"], __version__)

    def test_server_manifest_is_hidden_and_omits_visual_assets(self):
        manifest = json.loads((ROOT / "agent" / "dashboard" / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["tab"]["hidden"])
        self.assertEqual(manifest["entry"], "server-only.js")
        self.assertNotIn("css", manifest)
        self.assertFalse((ROOT / "agent" / "dashboard" / "dist").exists())

    def test_server_loader_shim_registers_no_visible_component(self):
        source = (ROOT / "agent" / "dashboard" / "server-only.js").read_text(encoding="utf-8").strip()
        self.assertIn('register("hermes-jev-performance", () => null)', source)
        self.assertLess(len(source.encode("utf-8")), 100)

    def test_install_doc_uses_native_hermes_lifecycle(self):
        text = (ROOT / "docs" / "INSTALL.md").read_text(encoding="utf-8")
        for command in (
            "hermes plugins install",
            "hermes plugins update",
            "hermes plugins remove",
            "hermes plugins doctor",
        ):
            self.assertIn(command, text)
        self.assertIn("hermes plugins disable", (ROOT / "docs" / "STATUS.md").read_text(encoding="utf-8") + (ROOT / "docs" / "INSTALL.md").read_text(encoding="utf-8"))
        self.assertNotIn("curl |", text)
        self.assertNotIn("wget |", text)

    def test_beginner_front_page_explains_all_three_install_choices(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for path in ("docs/INSTALL_SERVER.md", "docs/INSTALL_DESKTOP_WITH_VPS.md", "docs/INSTALL_LOCAL.md"):
            self.assertIn(path, text)
        self.assertIn("OFF", text)
        self.assertIn("ordinary language", text)
        self.assertIn("Hermes Desktop", text)
        self.assertIn("/agent", text)

    def test_fresh_install_mode_documentation_agrees(self):
        for path in ("README.md", "docs/INSTALL.md", "docs/INSTALL_SERVER.md", "docs/INSTALL_LOCAL.md"):
            with self.subTest(path=path):
                text = (ROOT / path).read_text(encoding="utf-8")
                self.assertRegex(text, r"(?i)(new installs|new installations|first installation).{0,100}OFF")
        old_install = (ROOT / "docs/INSTALL.md").read_text(encoding="utf-8")
        self.assertNotIn("defaults to SHADOW", old_install)


if __name__ == "__main__":
    unittest.main()
