from __future__ import annotations

import os
import shutil
import subprocess

from agents import RunContextWrapper, function_tool

from llm_autofix_agents.tools.context import APRToolContext, get_tool_context
from llm_autofix_agents.tools.paths import resolve_path
from llm_autofix_agents.tools.serialization import json_result
from llm_autofix_agents.tools.text import truncate


@function_tool
def apply_unified_diff(
    ctx: RunContextWrapper[APRToolContext],
    diff: str,
    cwd: str = ".",
    strip: int = 0,
    check_only: bool = False,
) -> str:
    """Apply a unified diff from a string using the system `patch` command."""
    cfg = get_tool_context(ctx)
    workdir = resolve_path(cfg, cwd)
    if shutil.which("patch") is None:
        return json_result({"ok": False, "error": "patch_command_not_found"})

    args = ["patch", f"-p{max(0, strip)}", "--forward", "--batch"]
    if check_only:
        args.append("--dry-run")
    try:
        completed = subprocess.run(
            args,
            cwd=str(workdir),
            input=diff,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "TERM": "dumb", "CI": "1", "NO_COLOR": "1"},
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout, stdout_truncated = truncate(exc.stdout or "", cfg.max_cmd_output_chars)
        stderr, stderr_truncated = truncate(exc.stderr or "", cfg.max_cmd_output_chars)
        return json_result(
            {
                "ok": False,
                "error": "timeout",
                "stdout": stdout,
                "stderr": stderr,
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated,
            }
        )

    stdout, stdout_truncated = truncate(completed.stdout, cfg.max_cmd_output_chars)
    stderr, stderr_truncated = truncate(completed.stderr, cfg.max_cmd_output_chars)
    return json_result(
        {
            "ok": completed.returncode == 0,
            "exit_code": completed.returncode,
            "cwd": cwd,
            "check_only": check_only,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }
    )
