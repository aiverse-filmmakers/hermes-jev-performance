import unittest

from jevperf.families import (
    FAMILY_CRITERIA,
    ROUTING_FAMILIES,
    filter_tools,
    tool_name,
)


def chat_tool(name):
    return {"type": "function", "function": {"name": name, "description": name}}


def responses_tool(name):
    return {"type": "function", "name": name, "description": name}


class FamilyTests(unittest.TestCase):
    def test_all_routing_families_have_criteria(self):
        self.assertEqual(set(ROUTING_FAMILIES), set(FAMILY_CRITERIA))
        self.assertEqual(len(ROUTING_FAMILIES), 11)

    def test_extracts_both_common_tool_schema_names(self):
        self.assertEqual(tool_name(chat_tool("web_search")), "web_search")
        self.assertEqual(tool_name(responses_tool("terminal")), "terminal")

    def test_web_filter_removes_known_competing_families(self):
        tools = [
            chat_tool("web_search"),
            chat_tool("terminal"),
            chat_tool("read_file"),
            chat_tool("tool_call"),
            chat_tool("clarify"),
            chat_tool("custom_future_tool"),
        ]
        filtered, applied, reason = filter_tools(tools, "web")
        names = [tool_name(tool) for tool in filtered]
        self.assertTrue(applied)
        self.assertEqual(reason, "filtered")
        self.assertIn("web_search", names)
        self.assertIn("clarify", names)
        self.assertIn("custom_future_tool", names)
        self.assertNotIn("terminal", names)
        self.assertIn("read_file", names)
        self.assertIn("tool_call", names)

    def test_github_keeps_repo_primitives(self):
        tools = [
            responses_tool("terminal"),
            responses_tool("read_file"),
            responses_tool("skill_view"),
            responses_tool("web_search"),
            responses_tool("tool_call"),
        ]
        filtered, applied, _ = filter_tools(tools, "github")
        names = [tool_name(tool) for tool in filtered]
        self.assertTrue(applied)
        self.assertEqual(names, ["terminal", "read_file", "skill_view", "tool_call"])

    def test_deferred_bridge_is_preserved_for_non_app_routes(self):
        tools = [
            responses_tool("web_search"),
            responses_tool("tool_search"),
            responses_tool("tool_describe"),
            responses_tool("tool_call"),
            responses_tool("terminal"),
        ]
        filtered, applied, _ = filter_tools(tools, "web")
        names = [tool_name(tool) for tool in filtered]
        self.assertTrue(applied)
        self.assertEqual(
            names,
            ["web_search", "tool_search", "tool_describe", "tool_call"],
        )

    def test_apps_keeps_bridge_and_mcp_tools(self):
        tools = [
            responses_tool("tool_call"),
            responses_tool("mcp__gmail__search"),
            responses_tool("web_search"),
            responses_tool("terminal"),
        ]
        filtered, applied, _ = filter_tools(tools, "apps")
        names = [tool_name(tool) for tool in filtered]
        self.assertTrue(applied)
        self.assertEqual(names, ["tool_call", "mcp__gmail__search"])

    def test_none_and_multi_are_never_filtered(self):
        tools = [responses_tool("web_search"), responses_tool("terminal")]
        for family in ("none", "multi", "none_of_these"):
            with self.subTest(family=family):
                filtered, applied, reason = filter_tools(tools, family)
                self.assertIs(filtered, tools)
                self.assertFalse(applied)
                self.assertEqual(reason, "unrestricted_family")

    def test_zero_family_match_fails_open(self):
        tools = [responses_tool("web_search"), responses_tool("terminal")]
        filtered, applied, reason = filter_tools(tools, "memory")
        self.assertIs(filtered, tools)
        self.assertFalse(applied)
        self.assertEqual(reason, "no_family_tools")


if __name__ == "__main__":
    unittest.main()
