from __future__ import annotations

import asyncio
import json
import subprocess
import tempfile
from pathlib import Path

from agents.tool_context import ToolContext

from apr_toolkit import (
    APRToolContext,
    apply_unified_diff,
    build_apr_tools,
    execute_command,
    git_diff_summary,
    git_status_summary,
    list_files,
    read_file,
    replace_in_file,
    replace_lines,
    run_test_target,
    search_files,
    write_file,
)


class DummyUsage:
    requests = 0
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0


def make_wrapper(root: str, tool_name: str) -> ToolContext[APRToolContext]:
    return ToolContext(
        context=APRToolContext(root_dir=root),
        usage=DummyUsage(),
        tool_name=tool_name,
        tool_call_id="tc_123",
        tool_arguments="{}",
    )


async def call(tool, root: str, payload: str):
    return json.loads(await tool.on_invoke_tool(make_wrapper(root, tool.name), payload))


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "src").mkdir()
        (root / "tests").mkdir()
        (root / "src" / "maths.py").write_text(
            "def add(a, b):\n    return a - b\n",
            encoding="utf-8",
        )
        (root / "tests" / "test_maths.py").write_text(
            "from src.maths import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
            encoding="utf-8",
        )
        (root / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\npythonpath = ['.']\n",
            encoding="utf-8",
        )

        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)

        res = await call(list_files, tmp, '{"glob":"src/**/*.py"}')
        assert res["ok"] is True and res["returned"] == 1

        res = await call(search_files, tmp, '{"pattern":"return a - b","glob":"src/**/*.py"}')
        assert res["returned"] == 1

        res = await call(read_file, tmp, '{"path":"src/maths.py"}')
        assert "1: def add(a, b):" in res["content"]

        res = await call(run_test_target, tmp, '{"target":"tests/test_maths.py","cwd":".","timeout_seconds":60}')
        assert res["ok"] is True and res["exit_code"] != 0

        res = await call(replace_in_file, tmp, '{"path":"src/maths.py","old":"return a - b","new":"return a + b","expected_occurrences":1}')
        assert res["ok"] is True

        res = await call(replace_lines, tmp, '{"path":"src/maths.py","start_line":1,"end_line":1,"new_lines":"def add(a, b):\\n"}')
        assert res["ok"] is True

        res = await call(write_file, tmp, '{"path":"notes.txt","content":"done\\n"}')
        assert res["ok"] is True

        res = await call(git_status_summary, tmp, '{}')
        assert res["ok"] is True and res["changed_files"] >= 1

        res = await call(git_diff_summary, tmp, '{}')
        assert res["ok"] is True and "src/maths.py" in res["summary"]

        diff = """--- notes.txt\n+++ notes.txt\n@@ -1 +1 @@\n-done\n+done fixed\n"""
        res = await call(apply_unified_diff, tmp, json.dumps({"diff": diff, "cwd": ".", "strip": 0}))
        assert res["exit_code"] == 0
        assert (root / "notes.txt").read_text(encoding="utf-8") == "done fixed\n"

        res = await call(execute_command, tmp, '{"command":"python -c \\\"print(2+3)\\\""}')
        assert res["ok"] is True and res["exit_code"] == 0 and res["stdout"].strip() == "5"

        tools = build_apr_tools("core")
        assert len(tools) >= 6

    print("all apr_toolkit tests passed")


asyncio.run(main())
