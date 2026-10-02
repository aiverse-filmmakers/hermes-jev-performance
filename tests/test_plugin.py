import importlib.util
import pathlib
import socket
import sys
import unittest
from unittest import mock

from tests.fakes import FakeContext


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_root_plugin():
    name = "hermes_jev_performance_plugin"
    spec = importlib.util.spec_from_file_location(
        name,
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None

    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
    return module


class PluginTests(unittest.TestCase):
    def test_registers_runtime_surfaces_without_network(self):
        module = load_root_plugin()
        ctx = FakeContext()

        with mock.patch.object(
            socket,
            "socket",
            side_effect=AssertionError("network access during plugin registration"),
        ):
            module.register(ctx)

        self.assertEqual(set(ctx.commands), {"jev"})
        self.assertEqual(set(ctx.middleware), {"llm_request"})
        self.assertEqual(len(ctx.middleware["llm_request"]), 1)
        self.assertEqual(
            set(ctx.hooks),
            {
                "pre_api_request",
                "post_api_request",
                "post_tool_call",
                "on_session_end",
                "transform_llm_output",
            },
        )
        self.assertEqual(set(ctx.cli_commands), {"jev"})

        command = ctx.commands["jev"]
        self.assertEqual(
            command["args_hint"],
            "[status|on|off|shadow|stats|notice on|notice off|help]",
        )
        self.assertIn("routing/performance", command["description"])

    def test_status_command_is_network_free(self):
        module = load_root_plugin()
        ctx = FakeContext()
        module.register(ctx)

        before = dict(ctx.settings)
        with mock.patch.object(
            socket,
            "socket",
            side_effect=AssertionError("network access during status"),
        ):
            output = ctx.commands["jev"]["handler"]("status")

        self.assertEqual(ctx.settings, before)
        self.assertIn("Phase: 6 (controls + telemetry)", output)
        self.assertIn("Last route: none yet", output)

    def test_degrades_without_optional_hook_and_cli_surfaces(self):
        module = load_root_plugin()
        ctx = FakeContext(hooks=False, cli=False)
        module.register(ctx)
        self.assertEqual(set(ctx.commands), {"jev"})
        self.assertEqual(set(ctx.middleware), {"llm_request"})
        self.assertEqual(ctx.hooks, {})
        self.assertEqual(ctx.cli_commands, {})


if __name__ == "__main__":
    unittest.main()
