from __future__ import annotations

import unittest

from llm_autofix_agents.tools.text import compact_test_output


class TestCompactTestOutput(unittest.TestCase):
    def test_collapse_repeated_blocks(self) -> None:
        block = ["line1", "line2", "line3"]
        lines = block * 4
        text = "\n".join(lines)

        result = compact_test_output(text, max_chars=4000)
        result_lines = result.splitlines()

        self.assertEqual(result_lines[:9], block * 3)
        self.assertEqual(result_lines[9], "[collapsed 1 repeated blocks]")

    def test_collapse_repeated_lines(self) -> None:
        text = "\n".join(["repeat"] * 8)
        result = compact_test_output(text, max_chars=4000)
        result_lines = result.splitlines()

        self.assertEqual(result_lines.count("repeat"), 3)
        self.assertTrue(any("[collapsed" in line for line in result_lines))

    def test_truncate_middle_preserves_tail(self) -> None:
        text = "start\n" + ("x" * 5000) + "\nTAIL"
        result = compact_test_output(text, max_chars=200)

        self.assertTrue(result.startswith("start"))
        self.assertTrue(result.endswith("TAIL"))
        self.assertIn("[truncated", result)

    def test_truncate_middle_respects_limit(self) -> None:
        text = "x" * 10000
        result = compact_test_output(text, max_chars=250)

        self.assertTrue(len(result) <= 250)

    def test_filters_syntax_warning_lines(self) -> None:
        text = (
            "youtube_dl/extractor/foo.py:39: SyntaxWarning: \"is not\" with a literal.\n"
            "  if error_code is not 0:\n"
            "======================================================================\n"
            "FAIL: test_something\n"
        )
        result = compact_test_output(text, max_chars=4000)

        self.assertNotIn("SyntaxWarning", result)
        self.assertNotIn("if error_code is not 0", result)
        self.assertIn("FAIL: test_something", result)

    def test_filters_deprecation_warning_lines(self) -> None:
        text = (
            "lib/module.py:12: DeprecationWarning: use new_api instead\n"
            "  old_api()\n"
            "FAILED (errors=1)\n"
        )
        result = compact_test_output(text, max_chars=4000)

        self.assertNotIn("DeprecationWarning", result)
        self.assertNotIn("old_api()", result)
        self.assertIn("FAILED (errors=1)", result)

    def test_preserves_non_warning_lines(self) -> None:
        text = "AssertionError: 7 != 6\nFAILED"
        result = compact_test_output(text, max_chars=4000)

        self.assertEqual(result, text)


if __name__ == "__main__":
    unittest.main()
