from __future__ import annotations

from typing import Any

from agents import FunctionTool

from llm_autofix_agents.tools.command_tools import execute_command
from llm_autofix_agents.tools.edit_tools import replace_in_file, replace_lines, write_file
from llm_autofix_agents.tools.fs_tools import get_workspace_info, list_files, read_file, search_files
from llm_autofix_agents.tools.git_tools import git_diff_summary, git_status_summary
from llm_autofix_agents.tools.observable import make_observable
from llm_autofix_agents.tools.patch_tools import apply_unified_diff
from llm_autofix_agents.tools.test_tools import run_test_target

APR_FUNCTION_TOOLS = [
    get_workspace_info,
    list_files,
    read_file,
    search_files,
    write_file,
    replace_in_file,
    replace_lines,
    execute_command,
    run_test_target,
    git_status_summary,
    git_diff_summary,
    apply_unified_diff,
]

APR_CORE_TOOLS = [
    get_workspace_info,
    list_files,
    read_file,
    search_files,
    replace_in_file,
    replace_lines,
    execute_command,
    run_test_target,
]

APR_SAFE_MINIMAL_TOOLS = [
    read_file,
    search_files,
    replace_in_file,
    execute_command,
]

# Handoff-specific tool profiles: each agent gets ONLY the tools it needs.
# This enforces role boundaries and prevents agents from doing other agents' work.
APR_TRIAGE_TOOLS = [
    get_workspace_info,
    list_files,
    read_file,
    search_files,
]

APR_LOCALIZER_TOOLS = [
    get_workspace_info,
    list_files,
    read_file,
    search_files,
    execute_command,
    run_test_target,
]

APR_PATCHER_TOOLS = [
    get_workspace_info,
    list_files,
    read_file,
    search_files,
    write_file,
    replace_in_file,
    replace_lines,
    execute_command,
    run_test_target,
]

APR_VALIDATOR_TOOLS = [
    get_workspace_info,
    list_files,
    read_file,
    search_files,
    execute_command,
    run_test_target,
    git_status_summary,
    git_diff_summary,
]


def build_apr_tools(profile: str = "full") -> list[Any]:
    """Return a predefined APR tool profile with observability wrapping."""
    profiles = {
        "minimal": APR_SAFE_MINIMAL_TOOLS,
        "core": APR_CORE_TOOLS,
        "full": APR_FUNCTION_TOOLS,
        "triage": APR_TRIAGE_TOOLS,
        "localizer": APR_LOCALIZER_TOOLS,
        "patcher": APR_PATCHER_TOOLS,
        "validator": APR_VALIDATOR_TOOLS,
    }
    try:
        raw = list(profiles[profile])
    except KeyError as exc:
        raise ValueError(f"Unknown APR tool profile: {profile}") from exc
    return [make_observable(t) if isinstance(t, FunctionTool) else t for t in raw]
