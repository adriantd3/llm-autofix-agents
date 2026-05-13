from __future__ import annotations

from typing import Any, Mapping

from agents import RunContextWrapper, function_tool

from llm_autofix_agents.tools.command_tools import run_shell
from llm_autofix_agents.tools.context import APRToolContext, get_tool_context
from llm_autofix_agents.tools.metadata import (
    ToolDescriptor,
    ToolResultKind,
    classify_json_envelope,
    make_json_result_summarizer,
)
from llm_autofix_agents.tools.registry import register
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


# ---------------------------------------------------------------------------
# Observability metadata (SH1)
# ---------------------------------------------------------------------------


def _args_git_status(args: Mapping[str, Any]) -> dict[str, Any]:
    return {"cwd": args.get("cwd")}


def _args_git_diff(args: Mapping[str, Any]) -> dict[str, Any]:
    return {"pathspec": args.get("pathspec"), "cwd": args.get("cwd")}


def _result_git_status(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {"ok": ok}
    if ok is True:
        summary["branch"] = payload.get("branch")
        summary["changed_files"] = payload.get("changed_files")
        summary["truncated"] = payload.get("truncated")
    else:
        summary["error"] = payload.get("error")
    return summary


def _result_git_diff(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    return {
        "ok": ok,
        "pathspec": payload.get("pathspec"),
        "patch_truncated": payload.get("patch_truncated") if ok is True else None,
        "error": payload.get("error") if ok is False else None,
    }


register(ToolDescriptor(
    name="git_status_summary",
    result_kind=ToolResultKind.JSON_ENVELOPE,
    summarize_args=_args_git_status,
    summarize_result=make_json_result_summarizer(_result_git_status),
    classify_status=classify_json_envelope,
))

register(ToolDescriptor(
    name="git_diff_summary",
    result_kind=ToolResultKind.JSON_ENVELOPE,
    summarize_args=_args_git_diff,
    summarize_result=make_json_result_summarizer(_result_git_diff),
    classify_status=classify_json_envelope,
))
