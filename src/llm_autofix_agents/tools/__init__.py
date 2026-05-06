from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from llm_autofix_agents.tools.command_tools import execute_command
    from llm_autofix_agents.tools.context import APRToolContext
    from llm_autofix_agents.tools.edit_tools import replace_in_file, replace_lines, write_file
    from llm_autofix_agents.tools.fs_tools import get_workspace_info, list_files, read_file, search_files
    from llm_autofix_agents.tools.git_tools import git_diff_summary, git_status_summary
    from llm_autofix_agents.tools.patch_tools import apply_unified_diff
    from llm_autofix_agents.tools.profiles import (
        APR_CORE_TOOLS,
        APR_FUNCTION_TOOLS,
        APR_SAFE_MINIMAL_TOOLS,
        build_apr_tools,
    )
    from llm_autofix_agents.tools.test_tools import run_test_target


_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "execute_command": ("llm_autofix_agents.tools.command_tools", "execute_command"),
    "APRToolContext": ("llm_autofix_agents.tools.context", "APRToolContext"),
    "replace_in_file": ("llm_autofix_agents.tools.edit_tools", "replace_in_file"),
    "replace_lines": ("llm_autofix_agents.tools.edit_tools", "replace_lines"),
    "write_file": ("llm_autofix_agents.tools.edit_tools", "write_file"),
    "get_workspace_info": ("llm_autofix_agents.tools.fs_tools", "get_workspace_info"),
    "list_files": ("llm_autofix_agents.tools.fs_tools", "list_files"),
    "read_file": ("llm_autofix_agents.tools.fs_tools", "read_file"),
    "search_files": ("llm_autofix_agents.tools.fs_tools", "search_files"),
    "git_diff_summary": ("llm_autofix_agents.tools.git_tools", "git_diff_summary"),
    "git_status_summary": ("llm_autofix_agents.tools.git_tools", "git_status_summary"),
    "apply_unified_diff": ("llm_autofix_agents.tools.patch_tools", "apply_unified_diff"),
    "APR_CORE_TOOLS": ("llm_autofix_agents.tools.profiles", "APR_CORE_TOOLS"),
    "APR_FUNCTION_TOOLS": ("llm_autofix_agents.tools.profiles", "APR_FUNCTION_TOOLS"),
    "APR_SAFE_MINIMAL_TOOLS": ("llm_autofix_agents.tools.profiles", "APR_SAFE_MINIMAL_TOOLS"),
    "build_apr_tools": ("llm_autofix_agents.tools.profiles", "build_apr_tools"),
    "run_test_target": ("llm_autofix_agents.tools.test_tools", "run_test_target"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value

__all__ = [
    "APRToolContext",
    "APR_FUNCTION_TOOLS",
    "APR_CORE_TOOLS",
    "APR_SAFE_MINIMAL_TOOLS",
    "build_apr_tools",
    "get_workspace_info",
    "list_files",
    "read_file",
    "search_files",
    "write_file",
    "replace_in_file",
    "replace_lines",
    "execute_command",
    "run_test_target",
    "git_status_summary",
    "git_diff_summary",
    "apply_unified_diff",
]
