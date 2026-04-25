from __future__ import annotations

from agents import RunContextWrapper, function_tool

from llm_autofix_agents.tools.command_tools import run_shell
from llm_autofix_agents.tools.context import APRToolContext, get_tool_context
from llm_autofix_agents.tools.paths import workspace_root
from llm_autofix_agents.tools.serialization import json_result
from llm_autofix_agents.tools.text import detect_test_command


@function_tool
def run_test_target(
    ctx: RunContextWrapper[APRToolContext],
    target: str | None = None,
    runner: str | None = None,
    cwd: str = ".",
    timeout_seconds: int | None = None,
) -> str:
    """Run a focused test command."""
    cfg = get_tool_context(ctx)
    root = workspace_root(cfg)
    if runner is None:
        detected = detect_test_command(root)
        if detected is None:
            return json_result({"ok": False, "error": "no_test_runner_detected"})
        runner = detected[1]
    command = runner if not target else f"{runner} {target}"
    timeout = timeout_seconds or cfg.default_test_timeout_seconds
    result = run_shell(cfg, command=command, cwd=cwd, timeout_seconds=timeout)
    result["tool"] = "run_test_target"
    result["target"] = target
    result["runner"] = runner
    return json_result(result)
