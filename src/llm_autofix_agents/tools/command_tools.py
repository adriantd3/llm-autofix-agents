from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from agents import RunContextWrapper, function_tool

from llm_autofix_agents.flow.execution.commands import CommandExecutor
from llm_autofix_agents.tools.context import APRToolContext, get_tool_context
from llm_autofix_agents.tools.metadata import (
    ToolDescriptor,
    ToolResultKind,
    classify_json_envelope,
    make_json_result_summarizer,
    truncate_str,
)
from llm_autofix_agents.tools.paths import resolve_path
from llm_autofix_agents.tools.registry import register
from llm_autofix_agents.tools.serialization import json_result
from llm_autofix_agents.tools.text import compact_test_output


def run_shell(cfg: APRToolContext, *, command: str, cwd: str = ".", timeout_seconds: int = 30) -> dict[str, object]:
    workdir = resolve_path(cfg, cwd)
    if not workdir.exists() or not workdir.is_dir():
        return {"ok": False, "error": "invalid_cwd", "cwd": cwd}

    execution = CommandExecutor(max_output_chars=cfg.max_cmd_output_chars).execute_command(
        command=command,
        cwd=workdir,
        timeout_seconds=timeout_seconds,
        use_bash_lc=True,
        env_overrides={
            "TERM": "dumb",
            "CI": "1",
            "PYTHONUNBUFFERED": "1",
            "PY_COLORS": "0",
            "NO_COLOR": "1",
        },
    )
    payload = asdict(execution)
    payload["stdout"] = compact_test_output(execution.stdout, max_chars=cfg.max_cmd_output_chars)
    payload["stderr"] = compact_test_output(execution.stderr, max_chars=cfg.max_cmd_output_chars)
    payload["ok"] = execution.error is None
    payload["cwd"] = cwd
    return payload


@function_tool
def execute_command(
    ctx: RunContextWrapper[APRToolContext],
    command: str,
    cwd: str = ".",
    timeout_seconds: int = 30,
) -> str:
    """Run a non-interactive shell command as `bash -lc <command>`."""
    cfg = get_tool_context(ctx)
    return json_result(run_shell(cfg, command=command, cwd=cwd, timeout_seconds=timeout_seconds))


# ---------------------------------------------------------------------------
# Observability metadata (SH1)
# ---------------------------------------------------------------------------


def _args_execute_command(args: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "command": truncate_str(str(args.get("command", "")), 200),
        "cwd": args.get("cwd"),
        "timeout_seconds": args.get("timeout_seconds"),
    }


def _result_execute_command(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ok": ok,
        "exit_code": payload.get("exit_code"),
        "timed_out": payload.get("timed_out"),
    }
    cmd = payload.get("command", "")
    if cmd:
        summary["command"] = truncate_str(str(cmd), 200)
    cwd = payload.get("cwd")
    if cwd:
        summary["cwd"] = cwd
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
    name="execute_command",
    result_kind=ToolResultKind.JSON_ENVELOPE,
    summarize_args=_args_execute_command,
    summarize_result=make_json_result_summarizer(_result_execute_command),
    classify_status=classify_json_envelope,
))
