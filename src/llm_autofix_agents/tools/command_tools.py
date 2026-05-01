from __future__ import annotations

from dataclasses import asdict

from agents import RunContextWrapper, function_tool

from llm_autofix_agents.flow.execution import CommandExecutor
from llm_autofix_agents.tools.context import APRToolContext, get_tool_context
from llm_autofix_agents.tools.paths import resolve_path
from llm_autofix_agents.tools.serialization import json_result


def run_shell(cfg: APRToolContext, *, command: str, cwd: str = ".", timeout_seconds: int = 30) -> dict[str, object]:
    workdir = resolve_path(cfg, cwd)
    if not workdir.exists() or not workdir.is_dir():
        return {"ok": False, "error": "invalid_cwd", "cwd": cwd}

    execution = CommandExecutor(max_output_chars=cfg.max_cmd_output_chars).run(
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
