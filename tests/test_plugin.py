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

    # Relative imports in a directory plugin require the package to exist in
    # sys.modules while its root __init__.py executes, which mirrors normal
    # package/plugin loading semantics.
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
    def test_registers_only_jev_command_and_does_not_touch_network(self):
        module = load_root_plugin()
        ctx = FakeContext()

        with mock.patch.object(
            socket,
            "socket",
            side_effect=AssertionError("network access during Phase 1 registration"),
        ):
            module.register(ctx)

        self.assertEqual(set(ctx.commands), {"jev"})
        self.assertEqual(set(ctx.middleware), {"llm_request"})
        self.assertEqual(len(ctx.middleware["llm_request"]), 1)
        command = ctx.commands["jev"]
        self.assertEqual(command["args_hint"], "[status|help]")
        self.assertIn("routing/performance", command["description"])

    def test_command_handler_is_read_only_and_network_free(self):
        module = load_root_plugin()
        ctx = FakeContext()
        module.register(ctx)

        before = dict(ctx.settings)
        with mock.patch.object(
            socket,
            "socket",
            side_effect=AssertionError("network access during Phase 1 status"),
        ):
            output = ctx.commands["jev"]["handler"]("status")

        self.assertEqual(ctx.settings, before)
        self.assertIn("Phase: 4 (routing middleware)", output)
        self.assertIn("Last route: none yet", output)


if __name__ == "__main__":
    unittest.main()
