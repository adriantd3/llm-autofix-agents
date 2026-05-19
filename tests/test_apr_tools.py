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


def make_wrapper(
    root: str,
    tool_name: str,
    ctx: APRToolContext | None = None,
) -> ToolContext[APRToolContext]:
    return ToolContext(
        context=ctx or APRToolContext(root_dir=root),
        usage=DummyUsage(),
        tool_name=tool_name,
        tool_call_id="tc_123",
        tool_arguments="{}",
    )


async def call(tool, root: str, payload: str, ctx: APRToolContext | None = None):
    return json.loads(await tool.on_invoke_tool(make_wrapper(root, tool.name, ctx=ctx), payload))


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

            # Shared context simulates a single APR iteration (same context object across all tool calls).
            iteration_ctx = APRToolContext(root_dir=tmp)

            res = asyncio.run(call(list_files, tmp, '{"glob":"src/**/*.py"}', ctx=iteration_ctx))
            self.assertTrue(res["ok"])
            self.assertEqual(res["returned"], 1)

            res = asyncio.run(call(search_files, tmp, '{"pattern":"return a - b","glob":"src/**/*.py"}', ctx=iteration_ctx))
            self.assertEqual(res["returned"], 1)

            res = asyncio.run(call(read_file, tmp, '{"path":"src/maths.py"}', ctx=iteration_ctx))
            self.assertIn("1: def add(a, b):", res["content"])

            # run_test_target requires at least one edit first — verify the guard fires correctly.
            res = asyncio.run(
                call(run_test_target, tmp, '{"target":"tests/test_maths.py","cwd":".","timeout_seconds":60}', ctx=iteration_ctx)
            )
            self.assertFalse(res["ok"])
            self.assertIn("no_changes_yet", res["error"])

            res = asyncio.run(
                call(
                    replace_in_file,
                    tmp,
                    '{"path":"src/maths.py","old":"return a - b","new":"return a + b","expected_occurrences":1}',
                    ctx=iteration_ctx,
                )
            )
            self.assertTrue(res["ok"])
            self.assertEqual(iteration_ctx.iteration_edit_count, 1)

            # After an edit, run_test_target should now be allowed and report the fix.
            res = asyncio.run(
                call(run_test_target, tmp, '{"target":"tests/test_maths.py","cwd":".","timeout_seconds":60}', ctx=iteration_ctx)
            )
            self.assertTrue(res["ok"])
            self.assertEqual(res["exit_code"], 0)

            res = asyncio.run(
                call(
                    replace_lines,
                    tmp,
                    '{"path":"src/maths.py","start_line":1,"end_line":1,"new_lines":"def add(a, b):\\n"}',
                    ctx=iteration_ctx,
                )
            )
            self.assertTrue(res["ok"])
            self.assertEqual(iteration_ctx.iteration_edit_count, 2)

            res = asyncio.run(call(write_file, tmp, '{"path":"notes.txt","content":"done\\n"}', ctx=iteration_ctx))
            self.assertTrue(res["ok"])
            self.assertEqual(iteration_ctx.iteration_edit_count, 3)

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


class RunTestTargetGuardTests(unittest.TestCase):
    def test_rejects_python_inline_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = asyncio.run(
                call(run_test_target, tmp, '{"runner":"python -c \\"import sys; sys.exit(0)\\""}')
            )
        self.assertFalse(res["ok"])
        self.assertIn("python_inline_not_allowed", res["error"])

    def test_rejects_python3_inline_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = asyncio.run(
                call(run_test_target, tmp, '{"runner":"python3 -c \\"print(1)\\""}')
            )
        self.assertFalse(res["ok"])
        self.assertIn("python_inline_not_allowed", res["error"])

    def test_allows_normal_runner(self) -> None:
        # A normal runner with python in the path but no -c flag should not be blocked.
        # We just verify no false positive is raised; the command itself will fail
        # because there is no test file, but ok/error will NOT be "python_inline_not_allowed".
        with tempfile.TemporaryDirectory() as tmp:
            res = asyncio.run(
                call(run_test_target, tmp, '{"runner":"python -m pytest nonexistent_test.py"}')
            )
        self.assertNotEqual(res.get("error", ""), "python_inline_not_allowed")


class RunTestTargetExit4RelaxationTests(unittest.TestCase):
    """Exit-code-4 relaxation: allow one pre-edit test call when baseline was a
    pytest collection failure. Observed in scrapy-33 trace (tools 5/8/20)."""

    def test_exit4_baseline_allows_first_pre_edit_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = APRToolContext(
                root_dir=tmp,
                iteration_edit_count=0,
                pre_edit_test_count=0,
                baseline_exit_code=4,
            )
            res = asyncio.run(
                call(
                    run_test_target,
                    tmp,
                    '{"runner":"echo collection-check"}',
                    ctx=ctx,
                )
            )
        # Should NOT be blocked by no_changes_yet
        self.assertNotEqual(res.get("error", ""), "no_changes_yet: apply a fix with replace_in_file or replace_lines before running tests")
        # pre_edit_test_count incremented
        self.assertEqual(ctx.pre_edit_test_count, 1)

    def test_exit4_baseline_blocks_second_pre_edit_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = APRToolContext(
                root_dir=tmp,
                iteration_edit_count=0,
                pre_edit_test_count=1,
                baseline_exit_code=4,
            )
            res = asyncio.run(
                call(
                    run_test_target,
                    tmp,
                    '{"runner":"echo should-be-blocked"}',
                    ctx=ctx,
                )
            )
        self.assertFalse(res["ok"])
        self.assertIn("no_changes_yet", res["error"])

    def test_exit1_baseline_always_blocks_pre_edit_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = APRToolContext(
                root_dir=tmp,
                iteration_edit_count=0,
                pre_edit_test_count=0,
                baseline_exit_code=1,
            )
            res = asyncio.run(
                call(
                    run_test_target,
                    tmp,
                    '{"runner":"echo should-be-blocked"}',
                    ctx=ctx,
                )
            )
        self.assertFalse(res["ok"])
        self.assertIn("no_changes_yet", res["error"])


if __name__ == "__main__":
    unittest.main()
