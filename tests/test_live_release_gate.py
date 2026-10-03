import os
import unittest

from scripts.live_release_gate import (
    GateResult,
    Proc,
    active_agent_smoke,
    active_profile_checks,
    isolated_lifecycle_checks,
    live_jev_smoke,
    report_payload,
)


class FakeRunner:
    def __init__(self):
        self.calls = []
        self.plugin_enabled = True
        self.plugin_present = True

    def __call__(self, argv, *, env=None, timeout=180.0):
        self.calls.append((list(argv), dict(env or {}), timeout))
        command = " ".join(argv)

        if argv[:3] == ["hermes", "plugins", "install"]:
            self.plugin_present = True
            self.plugin_enabled = "--enable" in argv
            return Proc(0, "ok\n", "")
        if command == "hermes plugins disable hermes-jev-performance":
            self.plugin_enabled = False
            return Proc(0, "ok\n", "")
        if command == "hermes plugins enable hermes-jev-performance":
            self.plugin_present = True
            self.plugin_enabled = True
            return Proc(0, "ok\n", "")
        if command == "hermes plugins remove hermes-jev-performance":
            self.plugin_present = False
            self.plugin_enabled = False
            return Proc(0, "ok\n", "")
        if command == "hermes plugins list":
            text = "hermes-jev-performance enabled\n" if self.plugin_present else "security-guidance enabled\n"
            return Proc(0, text, "")
        if command == "hermes jev status":
            if not self.plugin_enabled:
                return Proc(2, "", "unknown command")
            return Proc(0, "Hermes Jev Performance\nMode: shadow\n", "")
        if argv[:2] == ["hermes", "jev"] and not self.plugin_enabled:
            return Proc(2, "", "unknown command")
        return Proc(0, "ok\n", "")


class LiveReleaseGateTests(unittest.TestCase):
    def test_active_profile_checks_are_read_only(self):
        runner = FakeRunner()
        results = active_profile_checks(runner=runner)
        commands = [" ".join(call[0]) for call in runner.calls]

        self.assertTrue(all(result.status == "pass" for result in results))
        self.assertIn("hermes --version", commands)
        self.assertIn("hermes plugins doctor hermes-jev-performance --ci", commands)
        self.assertIn("hermes jev doctor --json", commands)
        self.assertIn("hermes jev status", commands)
        self.assertIn(
            "hermes jev benchmark --repeats 2 --warmups 0",
            commands,
        )
        self.assertFalse(any(" plugins disable " in f" {cmd} " for cmd in commands))
        self.assertFalse(any(" plugins remove " in f" {cmd} " for cmd in commands))
        self.assertFalse(any(" chat " in f" {cmd} " for cmd in commands))

    def test_lifecycle_requires_full_commit_sha(self):
        results = isolated_lifecycle_checks(
            source="owner/repo",
            ref="not-a-sha",
            runner=FakeRunner(),
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "fail")
        self.assertIn("40-character", results[0].detail)

    def test_lifecycle_uses_isolated_hermes_home_and_completes_cycle(self):
        runner = FakeRunner()
        results = isolated_lifecycle_checks(
            source="owner/repo",
            ref="a" * 40,
            runner=runner,
        )
        self.assertTrue(all(result.status == "pass" for result in results))
        homes = {
            call[1].get("HERMES_HOME")
            for call in runner.calls
            if call[1].get("HERMES_HOME")
        }
        self.assertEqual(len(homes), 1)
        self.assertNotIn(None, homes)

        commands = [" ".join(call[0]) for call in runner.calls]
        self.assertTrue(any("plugins install owner/repo --enable --ref" in cmd for cmd in commands))
        self.assertIn("hermes plugins disable hermes-jev-performance", commands)
        self.assertIn("hermes plugins enable hermes-jev-performance", commands)
        self.assertIn("hermes plugins remove hermes-jev-performance", commands)
        self.assertIn("hermes jev off", commands)
        self.assertIn("hermes jev shadow", commands)
        self.assertIn("hermes jev on", commands)
        by_name = {result.name: result for result in results}
        self.assertEqual(by_name["disabled_registration_absent"].status, "pass")
        self.assertEqual(by_name["post_enable_status"].status, "pass")
        self.assertEqual(by_name["post_remove_absence"].status, "pass")

    def test_live_jev_smoke_uses_profile_scoped_hermes_command(self):
        runner = FakeRunner()
        result = live_jev_smoke(runner=runner)
        self.assertEqual(result.status, "pass")
        self.assertEqual(runner.calls[-1][0], ["hermes", "jev", "smoke"])

    def test_active_agent_restores_original_mode(self):
        runner = FakeRunner()
        results = active_agent_smoke(runner=runner)
        commands = [" ".join(call[0]) for call in runner.calls]
        self.assertTrue(all(result.status == "pass" for result in results))
        self.assertEqual(commands[-1], "hermes jev shadow")
        self.assertEqual(
            [cmd for cmd in commands if " chat " in f" {cmd} "],
            [
                "hermes chat --oneshot -q Explain recursion in one sentence.",
                "hermes chat --oneshot -q Check how much RAM this machine is currently using.",
                "hermes chat --oneshot -q Search the public web for the official Hermes Agent repository and return its name.",
            ],
        )

    def test_active_agent_restores_mode_after_failure(self):
        calls = []

        def runner(argv, *, env=None, timeout=180.0):
            calls.append(list(argv))
            command = " ".join(argv)
            if command == "hermes jev status":
                return Proc(0, "Mode: on\n", "")
            if argv[:3] == ["hermes", "chat", "--oneshot"]:
                raise OSError("synthetic")
            return Proc(0, "ok\n", "")

        results = active_agent_smoke(runner=runner)
        self.assertEqual(calls[-1], ["hermes", "jev", "on"])
        self.assertTrue(any(result.status == "fail" for result in results))
        self.assertEqual(results[-1].name, "restore_original_mode")
        self.assertEqual(results[-1].status, "pass")

    def test_report_contains_no_raw_command_output(self):
        payload = report_payload(
            [
                GateResult("a", "pass", "safe"),
                GateResult("b", "manual", "manual check"),
            ]
        )
        self.assertEqual(payload["overall"], "manual")
        self.assertFalse(payload["privacy"]["raw_command_output_included"])
        self.assertFalse(payload["privacy"]["credentials_included"])

    def test_safe_env_does_not_mutate_process_environment(self):
        runner = FakeRunner()
        before = dict(os.environ)
        active_profile_checks(runner=runner)
        self.assertEqual(dict(os.environ), before)


if __name__ == "__main__":
    unittest.main()
