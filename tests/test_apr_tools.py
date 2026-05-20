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


class SearchFilesGuardTests(unittest.TestCase):
    """Hard search budget and duplicate-detection guards in search_files."""

    def test_blocks_exact_duplicate_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "foo.py").write_text("def foo(): return 1\n", encoding="utf-8")
            ctx = APRToolContext(root_dir=tmp)

            # First call succeeds
            res1 = asyncio.run(call(search_files, tmp, '{"pattern":"return 1","glob":"src/**/*.py"}', ctx=ctx))
            self.assertNotIn("duplicate_search", res1.get("error", ""))

            # Identical second call is rejected
            res2 = asyncio.run(call(search_files, tmp, '{"pattern":"return 1","glob":"src/**/*.py"}', ctx=ctx))
            self.assertFalse(res2["ok"])
            self.assertIn("duplicate_search", res2["error"])

    def test_budget_exhausted_blocks_pre_edit_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            budget = 3
            ctx = APRToolContext(root_dir=tmp, search_files_budget=budget, iteration_edit_count=0)

            # Exhaust the budget with distinct queries
            for i in range(budget):
                asyncio.run(call(search_files, tmp, f'{{"pattern":"pattern_{i}","glob":"src/**"}}', ctx=ctx))

            self.assertEqual(ctx.search_files_calls, budget)

            # Next distinct call must be blocked
            res = asyncio.run(call(search_files, tmp, '{"pattern":"pattern_overflow","glob":"src/**"}', ctx=ctx))
            self.assertFalse(res["ok"])
            self.assertIn("search_budget_exhausted", res["error"])

    def test_budget_lifted_after_edit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "foo.py").write_text("def foo(): return 1\n", encoding="utf-8")
            budget = 2
            # Simulate budget already exhausted, but an edit has been made
            ctx = APRToolContext(
                root_dir=tmp,
                search_files_budget=budget,
                search_files_calls=budget,
                iteration_edit_count=1,  # edit already applied
            )

            # Budget should not apply after an edit
            res = asyncio.run(call(search_files, tmp, '{"pattern":"return 1","glob":"src/**/*.py"}', ctx=ctx))
            self.assertNotIn("search_budget_exhausted", res.get("error", ""))

    # --- duplicate key correctness ---

    def test_regex_flag_distinguishes_duplicate_key(self) -> None:
        """regex=True and regex=False with the same pattern are DIFFERENT queries
        and must not trigger duplicate detection against each other."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "foo.py").write_text("def foo(): return 1\n", encoding="utf-8")
            ctx = APRToolContext(root_dir=tmp)

            # First call: literal search
            asyncio.run(call(search_files, tmp, '{"pattern":"return","glob":"src/**/*.py","regex":false}', ctx=ctx))
            # Second call: regex mode with same pattern — must NOT be blocked as duplicate
            res = asyncio.run(call(search_files, tmp, '{"pattern":"return","glob":"src/**/*.py","regex":true}', ctx=ctx))
            self.assertNotIn("duplicate_search", res.get("error", ""))
            self.assertEqual(ctx.search_files_calls, 2)

    def test_case_insensitive_pattern_is_a_duplicate(self) -> None:
        """With the default case_sensitive=False, 'FOO' and 'foo' match identically
        and must be treated as the same query (duplicate blocked)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "foo.py").write_text("def foo(): return 1\n", encoding="utf-8")
            ctx = APRToolContext(root_dir=tmp)

            asyncio.run(call(search_files, tmp, '{"pattern":"FOO","glob":"src/**/*.py"}', ctx=ctx))
            res = asyncio.run(call(search_files, tmp, '{"pattern":"foo","glob":"src/**/*.py"}', ctx=ctx))
            self.assertFalse(res["ok"])
            self.assertIn("duplicate_search", res["error"])

    def test_case_sensitive_true_different_casing_is_not_a_duplicate(self) -> None:
        """With case_sensitive=True, 'FOO' and 'foo' match different text and must
        be treated as distinct queries — no duplicate blocking."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "foo.py").write_text("def FOO(): return 1\ndef foo(): return 2\n", encoding="utf-8")
            ctx = APRToolContext(root_dir=tmp)

            asyncio.run(call(search_files, tmp, '{"pattern":"FOO","glob":"src/**/*.py","case_sensitive":true}', ctx=ctx))
            res = asyncio.run(call(search_files, tmp, '{"pattern":"foo","glob":"src/**/*.py","case_sensitive":true}', ctx=ctx))
            self.assertNotIn("duplicate_search", res.get("error", ""))
            self.assertEqual(ctx.search_files_calls, 2)

    def test_case_sensitive_flag_itself_differentiates_key(self) -> None:
        """cs=True and cs=False with the same lower-cased pattern are different
        queries (one is restricted to exact case, the other is not)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "foo.py").write_text("def foo(): return 1\n", encoding="utf-8")
            ctx = APRToolContext(root_dir=tmp)

            asyncio.run(call(search_files, tmp, '{"pattern":"foo","glob":"src/**/*.py","case_sensitive":false}', ctx=ctx))
            res = asyncio.run(call(search_files, tmp, '{"pattern":"foo","glob":"src/**/*.py","case_sensitive":true}', ctx=ctx))
            self.assertNotIn("duplicate_search", res.get("error", ""))
            self.assertEqual(ctx.search_files_calls, 2)

    def test_different_glob_is_not_a_duplicate(self) -> None:
        """Same pattern with different glob scopes must each be allowed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "foo.py").write_text("def foo(): pass\n", encoding="utf-8")
            ctx = APRToolContext(root_dir=tmp)

            asyncio.run(call(search_files, tmp, '{"pattern":"def foo","glob":"src/**/*.py"}', ctx=ctx))
            res = asyncio.run(call(search_files, tmp, '{"pattern":"def foo","glob":"**/*.py"}', ctx=ctx))
            self.assertNotIn("duplicate_search", res.get("error", ""))
            self.assertEqual(ctx.search_files_calls, 2)

    # --- state consistency ---

    def test_duplicate_error_does_not_consume_budget(self) -> None:
        """A blocked duplicate must not count against the search budget."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            ctx = APRToolContext(root_dir=tmp, search_files_budget=2)

            asyncio.run(call(search_files, tmp, '{"pattern":"x","glob":"src/**"}', ctx=ctx))
            self.assertEqual(ctx.search_files_calls, 1)

            # Trigger duplicate
            asyncio.run(call(search_files, tmp, '{"pattern":"x","glob":"src/**"}', ctx=ctx))
            # Counter must still be 1 — duplicate didn't consume a slot
            self.assertEqual(ctx.search_files_calls, 1)

            # Budget slot #2 is still available
            asyncio.run(call(search_files, tmp, '{"pattern":"y","glob":"src/**"}', ctx=ctx))
            self.assertEqual(ctx.search_files_calls, 2)

    def test_budget_error_does_not_modify_state(self) -> None:
        """A budget-exceeded rejection must leave both counters unchanged."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ctx = APRToolContext(root_dir=tmp, search_files_budget=1, search_files_calls=1)

            before_queries = dict(ctx.seen_search_queries)
            res = asyncio.run(call(search_files, tmp, '{"pattern":"z","glob":"**"}', ctx=ctx))

            self.assertFalse(res["ok"])
            self.assertIn("search_budget_exhausted", res["error"])
            self.assertEqual(ctx.search_files_calls, 1)  # unchanged
            self.assertEqual(ctx.seen_search_queries, before_queries)  # unchanged

    def test_duplicate_error_does_not_modify_seen_queries(self) -> None:
        """A duplicate rejection must not overwrite the original call number stored."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
            ctx = APRToolContext(root_dir=tmp)

            asyncio.run(call(search_files, tmp, '{"pattern":"x","glob":"src/**"}', ctx=ctx))
            original_call_number = ctx.seen_search_queries.copy()

            asyncio.run(call(search_files, tmp, '{"pattern":"x","glob":"src/**"}', ctx=ctx))
            # Seen queries must be unchanged after the duplicate was blocked
            self.assertEqual(ctx.seen_search_queries, original_call_number)

    def test_duplicate_error_takes_precedence_over_budget_exhausted(self) -> None:
        """When a query is both a duplicate AND the budget is exhausted, the
        duplicate error must be returned (checked first)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            ctx = APRToolContext(root_dir=tmp, search_files_budget=1)

            # First call: consumes the only slot
            asyncio.run(call(search_files, tmp, '{"pattern":"q","glob":"src/**"}', ctx=ctx))
            self.assertEqual(ctx.search_files_calls, 1)

            # Second call with the SAME pattern: budget is also exhausted.
            # Must get "duplicate", not "budget_exhausted".
            res = asyncio.run(call(search_files, tmp, '{"pattern":"q","glob":"src/**"}', ctx=ctx))
            self.assertFalse(res["ok"])
            self.assertIn("duplicate_search", res["error"])

    # --- invalid regex ---

    def test_invalid_regex_returns_error_without_consuming_slot(self) -> None:
        """An invalid regex (regex=True with bad pattern) must return a clean error
        and must NOT register the call in seen_search_queries or increment search_files_calls."""
        with tempfile.TemporaryDirectory() as tmp:
            ctx = APRToolContext(root_dir=tmp)

            res = asyncio.run(call(search_files, tmp, '{"pattern":"[invalid","glob":"**","regex":true}', ctx=ctx))

            self.assertFalse(res["ok"])
            self.assertIn("invalid_regex", res["error"])
            # Slot must NOT have been consumed
            self.assertEqual(ctx.search_files_calls, 0)
            self.assertEqual(ctx.seen_search_queries, {})

    def test_valid_call_succeeds_after_invalid_regex_attempt(self) -> None:
        """After a failed invalid-regex call, a valid call with the same pattern
        must succeed (the failed call must not appear in seen_search_queries)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "a.py").write_text("foo = 1\n", encoding="utf-8")
            ctx = APRToolContext(root_dir=tmp)

            # First: invalid regex — should fail cleanly
            asyncio.run(call(search_files, tmp, '{"pattern":"[invalid","glob":"src/**","regex":true}', ctx=ctx))

            # Retry with valid regex using the same pattern string — must NOT be blocked as duplicate
            res = asyncio.run(call(search_files, tmp, '{"pattern":"[invalid","glob":"src/**","regex":false}', ctx=ctx))
            self.assertNotIn("duplicate_search", res.get("error", ""))

    # --- budget boundary ---

    def test_budget_zero_allows_unlimited_calls(self) -> None:
        """budget=0 disables the limit; all calls must succeed regardless of count."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            ctx = APRToolContext(root_dir=tmp, search_files_budget=0)

            for i in range(15):
                res = asyncio.run(call(search_files, tmp, f'{{"pattern":"pattern_{i}","glob":"src/**"}}', ctx=ctx))
                self.assertNotIn("search_budget_exhausted", res.get("error", ""))

            self.assertEqual(ctx.search_files_calls, 15)

    def test_budget_last_allowed_call_succeeds(self) -> None:
        """The call at index budget-1 (last slot) must succeed, not be blocked."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            budget = 4
            ctx = APRToolContext(root_dir=tmp, search_files_budget=budget, search_files_calls=budget - 1)

            res = asyncio.run(call(search_files, tmp, '{"pattern":"last_allowed","glob":"src/**"}', ctx=ctx))
            self.assertNotIn("search_budget_exhausted", res.get("error", ""))
            self.assertEqual(ctx.search_files_calls, budget)

    def test_iteration_reset_clears_duplicate_state(self) -> None:
        """Simulating an iteration reset (as done by runner.py) must allow the
        same query to be searched again in the new iteration."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
            ctx = APRToolContext(root_dir=tmp)

            asyncio.run(call(search_files, tmp, '{"pattern":"x","glob":"src/**"}', ctx=ctx))
            self.assertEqual(ctx.search_files_calls, 1)

            # Simulate runner.py iteration reset
            ctx.iteration_edit_count = 0
            ctx.iteration_tool_call_count = 0
            ctx.pre_edit_test_count = 0
            ctx.search_files_calls = 0
            ctx.seen_search_queries = {}

            # Same query must now succeed
            res = asyncio.run(call(search_files, tmp, '{"pattern":"x","glob":"src/**"}', ctx=ctx))
            self.assertNotIn("duplicate_search", res.get("error", ""))
            self.assertEqual(ctx.search_files_calls, 1)


if __name__ == "__main__":
    unittest.main()
