"""Tool-family taxonomy and conservative filtering policy."""

from __future__ import annotations

from typing import Any


ROUTING_FAMILIES = (
    "github",
    "apps",
    "web",
    "terminal",
    "files",
    "memory",
    "skills",
    "media",
    "none",
    "multi",
    "none_of_these",
)

UNRESTRICTED_FAMILIES = frozenset({"none", "multi", "none_of_these"})

FAMILY_CRITERIA: dict[str, str] = {
    "none_of_these": "None of these categories fits, the request is ambiguous, or evidence is insufficient. Leave all tools available.",
    "github": (
        "GitHub repository work: repositories, pull requests, issues, Actions/workflows, "
        "commits, branches, releases, code changes, or GitHub inspection. Choose this only "
        "when GitHub/repository work is the main task and it does not also require an unrelated "
        "external tool family."
    ),
    "apps": (
        "Connected external apps/services or deferred MCP/app tools, such as email, calendar, "
        "cloud documents, Slack, creative services, schedulers, or other connected integrations. "
        "Do not choose this merely because GitHub is mentioned."
    ),
    "web": (
        "Public internet research, current online information, websites, browser research, "
        "search, extraction, or navigation where the public web is the main tool need."
    ),
    "terminal": (
        "Shell/system work: commands, processes, services, ports, packages, environment, "
        "machine diagnostics, scripts, or execution on the local/remote computer."
    ),
    "files": (
        "Local file work where reading, searching, writing, editing, or patching files is the "
        "main tool need and no other family is required."
    ),
    "memory": (
        "Retrieving or working with Hermes memory or previously remembered user context is the "
        "main tool need."
    ),
    "skills": (
        "Discovering, viewing, selecting, or managing Hermes skills is the main tool need."
    ),
    "media": (
        "Media-specific tool work such as image/vision analysis, speech/text-to-speech, audio, "
        "or other dedicated media tools."
    ),
    "none": (
        "The request can be answered directly without any external tool, file, memory, app, "
        "web, terminal, GitHub, skill, or media operation."
    ),
    "multi": (
        "The request genuinely requires two or more different tool families to complete, or a "
        "single-family restriction could prevent a necessary later step. Use this instead of "
        "guessing one family for mixed workflows."
    ),
}

# Hermes' Tool Search bridge is intentionally always preserved. llm_request
# middleware can filter the model-facing eager tool array, but current public
# Hermes APIs do not provide a supported way to re-scope the bridge's underlying
# deferred catalog after assembly. Removing the bridge can therefore hide a
# deferred tool that belongs to the selected semantic family (for example an
# installed GitHub plugin or deferred media tool). Jev routing is an optimization,
# not an authorization boundary, so capability preservation wins.
ALWAYS_KEEP = frozenset({
    "clarify",
    "delegate_task",
    "hermes_tool_search",
    "tool_search",
    "tool_describe",
    "tool_call",
    "jev_recover",
})

FAMILY_EXACT: dict[str, frozenset[str]] = {
    "github": frozenset({
        "terminal",
        "execute_code",
        "read_file",
        "write_file",
        "search_files",
        "patch",
        "skills_list",
        "skill_view",
        "skill_manage",
    }),
    "apps": frozenset({
        "hermes_tool_search",
        "tool_search",
        "tool_describe",
        "tool_call",
    }),
    "web": frozenset({
        "web_search",
        "web_extract",
        "browser_exec",
        "browser_vault_enter_code",
        "browser_vault_fill",
        "browser_vault_list",
        "browser_vault_save_login",
        "browser_vault_unlock",
    }),
    "terminal": frozenset({
        "terminal",
        "execute_code",
    }),
    "files": frozenset({
        "read_file",
        "write_file",
        "search_files",
        "patch",
    }),
    "memory": frozenset({
        "memory",
    }),
    "skills": frozenset({
        "skills_list",
        "skill_view",
        "skill_manage",
    }),
    "media": frozenset({
        "vision_analyze",
        "text_to_speech",
    }),
    "none": frozenset(),
    "multi": frozenset(),
}

FAMILY_PREFIXES: dict[str, tuple[str, ...]] = {
    "github": ("github_", "gh_"),
    "apps": ("mcp__", "mcp_"),
    "web": ("web_", "browser_"),
    "terminal": ("terminal_", "shell_", "exec_"),
    "files": ("file_", "files_"),
    "memory": ("memory_",),
    "skills": ("skill_", "skills_"),
    "media": ("vision_", "image_", "audio_", "speech_", "tts_"),
    "none": (),
    "multi": (),
}


def tool_name(tool: Any) -> str | None:
    """Extract a tool name from common Chat Completions/Responses schemas."""
    if not isinstance(tool, dict):
        return None

    direct = tool.get("name")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    function = tool.get("function")
    if isinstance(function, dict):
        name = function.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()

    return None


def _matches_family(name: str, family: str) -> bool:
    if name in FAMILY_EXACT.get(family, ()):
        return True
    return any(name.startswith(prefix) for prefix in FAMILY_PREFIXES.get(family, ()))


def _known_by_any_family(name: str) -> bool:
    return any(_matches_family(name, family) for family in FAMILY_EXACT)


def filter_tools(tools: Any, family: str) -> tuple[Any, bool, str]:
    """Filter known tools conservatively.

    Unknown tools and Hermes' deferred-tool bridge are preserved rather than
    accidentally removing capabilities. Known eager tools from other families
    are removed. If the selected family has no usable eager tool in the request,
    the original list is returned unchanged.
    """
    if family in UNRESTRICTED_FAMILIES:
        return tools, False, "unrestricted_family"
    if family not in FAMILY_EXACT or not isinstance(tools, list):
        return tools, False, "invalid_or_missing_tools"

    filtered: list[Any] = []
    matched_family = False

    for tool in tools:
        name = tool_name(tool)
        if name is None:
            filtered.append(tool)
            continue
        if name in ALWAYS_KEEP:
            filtered.append(tool)
            continue
        if _matches_family(name, family):
            matched_family = True
            filtered.append(tool)
            continue
        if _known_by_any_family(name):
            continue

        # Unknown/custom tools fail open. This preserves compatibility with tools
        # added by newer Hermes versions or third-party plugins.
        filtered.append(tool)

    if not matched_family:
        return tools, False, "no_family_tools"
    if len(filtered) == len(tools):
        return tools, False, "no_effect"
    return filtered, True, "filtered"
