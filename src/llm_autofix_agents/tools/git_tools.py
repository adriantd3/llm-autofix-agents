from __future__ import annotations

from agents import RunContextWrapper, function_tool

from llm_autofix_agents.tools.command_tools import run_shell
from llm_autofix_agents.tools.context import APRToolContext, get_tool_context
from llm_autofix_agents.tools.serialization import json_result
from llm_autofix_agents.tools.text import truncate


@function_tool
def git_status_summary(
    ctx: RunContextWrapper[APRToolContext],
    cwd: str = ".",
) -> str:
    """Return a compact git status summary for the workspace."""
    cfg = get_tool_context(ctx)
    status = run_shell(cfg, command="git status --short --branch", cwd=cwd, timeout_seconds=20)
    if not status.get("ok"):
        return json_result(status)
    if status.get("exit_code") != 0:
        return json_result({"ok": False, "error": "git_status_failed", **status})
    lines = [line for line in str(status.get("stdout", "")).splitlines() if line.strip()]
    branch = lines[0] if lines else ""
    changes = lines[1:] if len(lines) > 1 else []
    return json_result(
        {
            "ok": True,
            "branch": branch,
            "changed_files": len(changes),
            "changes": changes[:100],
            "truncated": len(changes) > 100,
        }
    )


@function_tool
def git_diff_summary(
    ctx: RunContextWrapper[APRToolContext],
    pathspec: str | None = None,
    cwd: str = ".",
) -> str:
    """Return a compact git diff summary and truncated patch text."""
    cfg = get_tool_context(ctx)
    summary_cmd = "git diff --stat"
    patch_cmd = "git diff --unified=3 --minimal"
    if pathspec:
        summary_cmd += f" -- {pathspec}"
        patch_cmd += f" -- {pathspec}"
    summary = run_shell(cfg, command=summary_cmd, cwd=cwd, timeout_seconds=20)
    patch = run_shell(cfg, command=patch_cmd, cwd=cwd, timeout_seconds=20)
    if summary.get("exit_code") != 0:
        return json_result({"ok": False, "error": "git_diff_failed", "summary": summary, "patch": patch})
    patch_text, patch_truncated = truncate(str(patch.get("stdout", "")), cfg.max_read_chars)
    return json_result(
        {
            "ok": True,
            "pathspec": pathspec,
            "summary": summary.get("stdout", ""),
            "patch": patch_text,
            "patch_truncated": patch_truncated,
        }
    )
