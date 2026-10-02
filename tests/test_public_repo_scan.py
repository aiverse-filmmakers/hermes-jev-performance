import pathlib
import tempfile
import unittest

from scripts.public_repo_scan import scan_repository, scan_text


class PublicRepoScanTests(unittest.TestCase):
    def test_detects_secret_shapes_without_embedding_a_real_fixture_in_source(self):
        token = "sk-" + "or-v1-" + ("A" * 24)
        findings = scan_text(token)
        self.assertIn("openrouter_token", findings)

        github = "gh" + "p_" + ("B" * 30)
        self.assertIn("github_classic_token", scan_text(github))

    def test_detects_non_placeholder_credential_assignment(self):
        line = "OPENROUTER_API_KEY" + "=" + ("secret" + "value")
        self.assertIn("credential_assignment", scan_text(line))

    def test_allows_documented_empty_or_placeholder_assignments(self):
        self.assertEqual(scan_text("OPENROUTER_API_KEY" + "=<TOKEN>\n"), set())
        self.assertEqual(scan_text("OPENROUTER_API_KEY" + '=""\n'), set())

    def test_detects_cross_platform_personal_user_paths(self):
        linux = "/" + "home/example-user/.hermes/config.yaml"
        mac = "/" + "Users/example-user/.hermes/config.yaml"
        windows = "C:" + "\\Users\\example-user\\.hermes\\config.yaml"
        self.assertIn("linux_user_path", scan_text(linux))
        self.assertIn("mac_user_path", scan_text(mac))
        self.assertIn("windows_user_path", scan_text(windows))

    def test_detects_non_example_email(self):
        address = "person" + "@private-domain.test"
        self.assertIn("email_address", scan_text(address))
        self.assertNotIn("email_address", scan_text("user" + "@example.com"))

    def test_detects_realistic_ipv4_but_allows_loopback_and_test_nets(self):
        address = "93." + "184.216.34"
        self.assertIn("ipv4_address", scan_text(address))
        self.assertNotIn("ipv4_address", scan_text("127." + "0.0.1"))
        self.assertNotIn("ipv4_address", scan_text("192." + "0.2.44"))
        self.assertNotIn("ipv4_address", scan_text("198." + "51.100.9"))
        self.assertNotIn("ipv4_address", scan_text("203." + "0.113.7"))

    def test_repository_scan_reports_rule_ids_without_secret_values(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = pathlib.Path(temp.name)
        secret = "gh" + "p_" + ("B" * 30)
        (root / "example.md").write_text(
            "GITHUB_TOKEN" + "=" + secret,
            encoding="utf-8",
        )
        findings = scan_repository(root)
        self.assertEqual(
            findings,
            [
                ("example.md", "credential_assignment"),
                ("example.md", "github_classic_token"),
            ],
        )
        self.assertNotIn(secret, repr(findings))


if __name__ == "__main__":
    unittest.main()
