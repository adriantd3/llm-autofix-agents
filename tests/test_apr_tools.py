from __future__ import annotations

import asyncio
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from agents.tool_context import ToolContext

from llm_autofix_agents.tools import (
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


class APRToolkitTests(unittest.TestCase):
    def test_core_tools_behave_like_demo_toolkit(self) -> None:
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

            res = asyncio.run(call(list_files, tmp, '{"glob":"src/**/*.py"}'))
            self.assertTrue(res["ok"])
            self.assertEqual(res["returned"], 1)

            res = asyncio.run(call(search_files, tmp, '{"pattern":"return a - b","glob":"src/**/*.py"}'))
            self.assertEqual(res["returned"], 1)

            res = asyncio.run(call(read_file, tmp, '{"path":"src/maths.py"}'))
            self.assertIn("1: def add(a, b):", res["content"])

            res = asyncio.run(
                call(run_test_target, tmp, '{"target":"tests/test_maths.py","cwd":".","timeout_seconds":60}')
            )
            self.assertTrue(res["ok"])
            self.assertNotEqual(res["exit_code"], 0)

            res = asyncio.run(
                call(
                    replace_in_file,
                    tmp,
                    '{"path":"src/maths.py","old":"return a - b","new":"return a + b","expected_occurrences":1}',
                )
            )
            self.assertTrue(res["ok"])

            res = asyncio.run(
                call(
                    replace_lines,
                    tmp,
                    '{"path":"src/maths.py","start_line":1,"end_line":1,"new_lines":"def add(a, b):\\n"}',
                )
            )
            self.assertTrue(res["ok"])

            res = asyncio.run(call(write_file, tmp, '{"path":"notes.txt","content":"done\\n"}'))
            self.assertTrue(res["ok"])

            res = asyncio.run(call(git_status_summary, tmp, "{}"))
            self.assertTrue(res["ok"])
            self.assertGreaterEqual(res["changed_files"], 1)

            res = asyncio.run(call(git_diff_summary, tmp, "{}"))
            self.assertTrue(res["ok"])
            self.assertIn("src/maths.py", res["summary"])

            diff = """--- notes.txt
+++ notes.txt
@@ -1 +1 @@
-done
+done fixed
"""
            res = asyncio.run(call(apply_unified_diff, tmp, json.dumps({"diff": diff, "cwd": ".", "strip": 0})))
            self.assertEqual(res["exit_code"], 0)
            self.assertEqual((root / "notes.txt").read_text(encoding="utf-8"), "done fixed\n")

            res = asyncio.run(call(execute_command, tmp, '{"command":"python -c \\"print(2+3)\\""}'))
            self.assertTrue(res["ok"])
            self.assertEqual(res["exit_code"], 0)
            self.assertEqual(res["stdout"].strip(), "5")

            tools = build_apr_tools("core")
            self.assertGreaterEqual(len(tools), 6)


if __name__ == "__main__":
    unittest.main()
