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


if __name__ == "__main__":
    unittest.main()
