from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from agents import RunContextWrapper, function_tool

from llm_autofix_agents.tools.command_tools import run_shell
from llm_autofix_agents.tools.context import APRToolContext, get_tool_context
from llm_autofix_agents.tools.metadata import (
    ToolDescriptor,
    ToolResultKind,
    classify_json_envelope,
    make_json_result_summarizer,
    truncate_str,
)
from llm_autofix_agents.tools.paths import workspace_root
from llm_autofix_agents.tools.registry import register
from llm_autofix_agents.tools.serialization import json_result
from llm_autofix_agents.tools.text import detect_test_command


_PYTHON_INLINE_RE = re.compile(r"\bpython[23]?\s+-c\b")


def _target_looks_like_command(target: str) -> bool:
    """Return True if target contains shell metacharacters that indicate a full command.

    The agent sometimes passes the entire test command as `target` in addition to `runner`,
    producing a double-command like `<cmd> <cmd>`.  Metacharacters or flag prefixes are a
    reliable signal that the agent confused the two arguments.
    """
    return any(c in target for c in ("&&", "||", ";", "|", "$(", "`", " -"))


@function_tool
def run_test_target(
    ctx: RunContextWrapper[APRToolContext],
    target: str | None = None,
    runner: str | None = None,
    cwd: str = ".",
    timeout_seconds: int | None = None,
) -> str:
    """Run a test command and return exit code and output.

    runner: the full test command verbatim (e.g. ". env/bin/activate && bash bugsinpy_run_test.sh").
    target: optional test class or function name appended after runner. Leave empty to run all tests.
            NEVER put the full command here — that causes double-execution and corrupts the run.
    cwd: working directory path. Use "" or "." for the workspace root. NEVER pass a file path here.
    """
    cfg = get_tool_context(ctx)
    root = workspace_root(cfg)
    if runner is None:
        detected = detect_test_command(root)
        if detected is None:
            return json_result({"ok": False, "error": "no_test_runner_detected"})
        runner = detected[1]
    if _PYTHON_INLINE_RE.search(runner):
        return json_result({
            "ok": False,
            "error": (
                "python_inline_not_allowed: use replace_in_file to apply your fix first, "
                "then run the actual test command (e.g. bash bugsinpy_run_test.sh)"
            ),
        })
    # Drop target if it looks like a full command — prevents the double-command failure mode
    # where the agent sets runner=<full cmd> AND target=<full cmd>, corrupting the shell call.
    safe_target = target if target and not _target_looks_like_command(target) else None
    command = runner if not safe_target else f"{runner} {safe_target}"
    timeout = timeout_seconds or cfg.default_test_timeout_seconds
    result = run_shell(cfg, command=command, cwd=cwd, timeout_seconds=timeout)
    result["tool"] = "run_test_target"
    result["target"] = safe_target
    result["runner"] = runner
    return json_result(result)


# ---------------------------------------------------------------------------
# Observability metadata (SH1)
# ---------------------------------------------------------------------------


def _args_run_test_target(args: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "target": args.get("target"),
        "runner": args.get("runner"),
        "cwd": args.get("cwd"),
        "timeout_seconds": args.get("timeout_seconds"),
    }


def _result_run_test_target(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ok": ok,
        "exit_code": payload.get("exit_code"),
        "timed_out": payload.get("timed_out"),
        "target": payload.get("target"),
        "runner": payload.get("runner"),
    }
    cmd = payload.get("command", "")
    if cmd:
        summary["command"] = truncate_str(str(cmd), 200)
    stdout = payload.get("stdout", "")
    stderr = payload.get("stderr", "")
    if stdout:
        summary["stdout_chars"] = len(str(stdout))
    if stderr:
        summary["stderr_chars"] = len(str(stderr))
    if ok is False:
        summary["error"] = payload.get("error")
    return summary


register(ToolDescriptor(
    name="run_test_target",
    result_kind=ToolResultKind.JSON_ENVELOPE,
    summarize_args=_args_run_test_target,
    summarize_result=make_json_result_summarizer(_result_run_test_target),
    classify_status=classify_json_envelope,
))
