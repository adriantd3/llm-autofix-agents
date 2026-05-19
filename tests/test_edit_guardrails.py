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


class WriteTruncationGuardTests(unittest.TestCase):
    def _make_large_file(self, root: Path, name: str, line_count: int) -> Path:
        p = root / name
        p.write_text("\n".join(f"line {i}" for i in range(line_count)) + "\n", encoding="utf-8")
        return p

    def test_blocks_when_new_content_is_less_than_two_thirds_of_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # 120-line file; write 60 lines (50% — below 2/3 threshold = 80 lines) → blocked.
            # This mirrors the real e2e case: agent wrote ~600 lines to a 1163-line file (51%).
            self._make_large_file(root, "utils.py", 120)
            new_content = "\n".join(f"# line {i}" for i in range(60)) + "\n"
            payload = json.dumps({"path": "utils.py", "content": new_content})
            res = asyncio.run(call(write_file, tmp, payload))
            self.assertFalse(res["ok"])
            self.assertEqual(res["error"], "write_file_would_truncate")
            self.assertIn("Use replace_in_file", res["message"])

    def test_blocks_stub_write_to_large_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # 60-line file; write 5 lines (8% — well below 2/3) → blocked
            self._make_large_file(root, "utils.py", 60)
            res = asyncio.run(
                call(write_file, tmp, '{"path":"utils.py","content":"# stub\\n"}')
            )
            self.assertFalse(res["ok"])
            self.assertEqual(res["error"], "write_file_would_truncate")

    def test_allows_overwrite_when_new_content_is_large_enough(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # 60-line file; write 45 lines (75% — above 2/3 threshold = 40) → allowed
            self._make_large_file(root, "utils.py", 60)
            new_content = "\n".join(f"# line {i}" for i in range(45)) + "\n"
            payload = json.dumps({"path": "utils.py", "content": new_content})
            res = asyncio.run(call(write_file, tmp, payload))
            self.assertTrue(res["ok"])

    def test_allows_creating_new_file_with_any_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = asyncio.run(
                call(write_file, tmp, '{"path":"new_file.py","content":"x\\n"}')
            )
            self.assertTrue(res["ok"])

    def test_allows_overwrite_of_small_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # 10-line file — guard only kicks in for >50 lines
            self._make_large_file(root, "small.py", 10)
            res = asyncio.run(
                call(write_file, tmp, '{"path":"small.py","content":"x\\n"}')
            )
            self.assertTrue(res["ok"])


class FuzzyReplaceTests(unittest.TestCase):
    def test_exact_match_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
            res = asyncio.run(
                call(replace_in_file, tmp, '{"path":"src.py","old":"    return 1","new":"    return 2"}')
            )
            self.assertTrue(res["ok"])
            self.assertNotIn("fuzzy_matched", res)

    def test_fuzzy_crlf_mismatch_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Python's read_text() normalizes file CRLF→LF on read, so the runtime-visible
            # mismatch is the reverse: LLM produces \r\n in old text (e.g., Windows clipboard)
            # but the stored source already has \n.  Pass 2 normalizes both sides.
            (root / "src.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
            payload = json.dumps({
                "path": "src.py",
                "old": "def foo():\r\n    return 1",  # CRLF from LLM
                "new": "def foo():\n    return 2",
            })
            res = asyncio.run(call(replace_in_file, tmp, payload))
            self.assertTrue(res["ok"])
            self.assertTrue(res.get("fuzzy_matched"))

    def test_fuzzy_trailing_whitespace_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Source has trailing spaces; LLM strips them in old text
            (root / "src.py").write_text("def foo():  \n    return 1   \n", encoding="utf-8")
            # old text has no trailing spaces (as LLM would produce)
            payload = json.dumps({
                "path": "src.py",
                "old": "def foo():\n    return 1",
                "new": "def foo():\n    return 2",
            })
            res = asyncio.run(call(replace_in_file, tmp, payload))
            self.assertTrue(res["ok"])
            self.assertTrue(res.get("fuzzy_matched"))

    def test_not_found_still_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
            res = asyncio.run(
                call(replace_in_file, tmp, '{"path":"src.py","old":"completely wrong text","new":"x"}')
            )
            self.assertFalse(res["ok"])
            self.assertEqual(res["error"], "old_text_not_found")

    def test_replace_all_requires_exact_match(self) -> None:
        # replace_all=True must not fall back to fuzzy (ambiguous multi-match semantics)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src.py").write_bytes(b"foo\r\nfoo\r\n")
            res = asyncio.run(
                call(replace_in_file, tmp, '{"path":"src.py","old":"foo","new":"bar","replace_all":true}')
            )
            # exact match exists (no CRLF in old), so this should succeed normally
            self.assertTrue(res["ok"])

    def test_replace_in_file_not_found_includes_file_size_hint(self) -> None:
        """When old text is not found, the error response should include file_size_lines
        and a hint so the agent knows to re-read instead of blindly retrying.
        Observed in thefuck-1 iter 2 (tools 10/12/20) and tqdm-1 iter 1 (tools 11/13):
        agent retried with stale text, wasting turns.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = "\n".join(f"line {i}" for i in range(1, 21))  # 20 lines
            (root / "module.py").write_text(content, encoding="utf-8")
            res = asyncio.run(
                call(
                    replace_in_file,
                    tmp,
                    '{"path":"module.py","old":"this text does not exist anywhere","new":"replacement"}',
                )
            )
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "old_text_not_found")
        self.assertIn("file_size_lines", res)
        self.assertEqual(res["file_size_lines"], 20)
        self.assertIn("hint", res)
        self.assertIn("current_file_preview", res)
        self.assertIn("line 1", res["current_file_preview"])
        self.assertIn("line 20", res["current_file_preview"])

    def test_replace_in_file_not_found_preview_truncated_for_large_file(self) -> None:
        """Files larger than 80 lines include a truncation notice in the preview."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = "\n".join(f"line {i}" for i in range(1, 102))  # 101 lines
            (root / "big.py").write_text(content, encoding="utf-8")
            res = asyncio.run(
                call(
                    replace_in_file,
                    tmp,
                    '{"path":"big.py","old":"this text does not exist anywhere","new":"replacement"}',
                )
            )
        self.assertFalse(res["ok"])
        self.assertEqual(res["file_size_lines"], 101)
        self.assertIn("more lines", res["current_file_preview"])


if __name__ == "__main__":
    unittest.main()
