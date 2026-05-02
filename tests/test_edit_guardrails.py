from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from agents.tool_context import ToolContext

# Pre-import orchestrator to break circular dependency when tools are imported
import llm_autofix_agents.flow.orchestrator  # noqa: F401
from llm_autofix_agents.tools.context import APRToolContext
from llm_autofix_agents.tools.edit_tools import replace_in_file, replace_lines, write_file


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


class EditGuardrailTests(unittest.TestCase):
    def test_write_file_rejects_test_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = asyncio.run(call(write_file, tmp, '{"path":"tests/test_foo.py","content":"pass"}'))
            self.assertFalse(res["ok"])
            self.assertEqual(res["error"], "test_file_modification_forbidden")
            self.assertIn("FORBIDDEN", res["message"])

    def test_write_file_rejects_test_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = asyncio.run(call(write_file, tmp, '{"path":"test/testdata/player.js","content":"x"}'))
            self.assertFalse(res["ok"])
            self.assertEqual(res["error"], "test_file_modification_forbidden")

    def test_replace_in_file_rejects_test_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            (root / "tests" / "test_maths.py").write_text("old", encoding="utf-8")
            res = asyncio.run(call(replace_in_file, tmp, '{"path":"tests/test_maths.py","old":"old","new":"new"}'))
            self.assertFalse(res["ok"])
            self.assertEqual(res["error"], "test_file_modification_forbidden")

    def test_replace_lines_rejects_test_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            (root / "tests" / "test_maths.py").write_text("line1\nline2", encoding="utf-8")
            res = asyncio.run(
                call(replace_lines, tmp, '{"path":"tests/test_maths.py","start_line":1,"end_line":1,"new_lines":"x"}')
            )
            self.assertFalse(res["ok"])
            self.assertEqual(res["error"], "test_file_modification_forbidden")

    def test_edit_tools_allow_source_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "maths.py").write_text("old", encoding="utf-8")
            res = asyncio.run(call(write_file, tmp, '{"path":"src/maths.py","content":"new"}'))
            self.assertTrue(res["ok"])

            res = asyncio.run(call(replace_in_file, tmp, '{"path":"src/maths.py","old":"new","new":"fixed"}'))
            self.assertTrue(res["ok"])

            res = asyncio.run(
                call(replace_lines, tmp, '{"path":"src/maths.py","start_line":1,"end_line":1,"new_lines":"line"}')
            )
            self.assertTrue(res["ok"])

    def test_rejects_files_starting_with_test_underscore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = asyncio.run(call(write_file, tmp, '{"path":"src/test_helper.py","content":"x"}'))
            self.assertFalse(res["ok"])
            self.assertEqual(res["error"], "test_file_modification_forbidden")

    def test_rejects_files_ending_with_underscore_test(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = asyncio.run(call(write_file, tmp, '{"path":"src/helper_test.py","content":"x"}'))
            self.assertFalse(res["ok"])
            self.assertEqual(res["error"], "test_file_modification_forbidden")


if __name__ == "__main__":
    unittest.main()
