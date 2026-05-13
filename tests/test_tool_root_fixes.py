"""Unit tests for the four root-cause fixes from the 2026-05-12 trace analysis.

Covered:
- _target_looks_like_command (test_tools)
- _find_test_function_using with class methods (iteration policy)
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from llm_autofix_agents.flow.policies.iteration import _find_test_function_using
from llm_autofix_agents.tools.test_tools import _target_looks_like_command


class TargetLooksLikeCommandTests(unittest.TestCase):
    def test_plain_test_path_is_safe(self) -> None:
        self.assertFalse(_target_looks_like_command("test/test_utils.py"))

    def test_class_path_is_safe(self) -> None:
        self.assertFalse(_target_looks_like_command("test_utils.py::TestXml"))

    def test_empty_is_safe(self) -> None:
        self.assertFalse(_target_looks_like_command(""))

    def test_full_command_with_flag_is_detected(self) -> None:
        # The double-command failure mode: agent passes `. env/bin/activate && bash run.sh -v`
        self.assertTrue(_target_looks_like_command(". env/bin/activate && bash run.sh"))

    def test_pipe_is_detected(self) -> None:
        self.assertTrue(_target_looks_like_command("pytest | tee output.txt"))

    def test_flag_prefix_is_detected(self) -> None:
        # `. env/bin/activate && bash bugsinpy_run_test.sh` often passed with `-v` flag
        self.assertTrue(_target_looks_like_command("bash run.sh -v"))

    def test_subshell_is_detected(self) -> None:
        self.assertTrue(_target_looks_like_command("$(which pytest)"))

    def test_semicolon_is_detected(self) -> None:
        self.assertTrue(_target_looks_like_command("cmd1; cmd2"))


class FindTestFunctionClassMethodTests(unittest.TestCase):
    """Verify that _find_test_function_using finds test methods inside classes."""

    def _write(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")

    def test_finds_top_level_test_function(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "test_utils.py"
            self._write(f, "def test_foo():\n    assert fix_xml_ampersands('&') == '&amp;'\n")
            result = _find_test_function_using(f, "fix_xml_ampersands", Path(tmp))
            self.assertIn("test_foo", result)
            self.assertIn("fix_xml_ampersands", result)

    def test_finds_class_method_test_function(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "test_utils.py"
            self._write(
                f,
                "import unittest\n"
                "class TestXml(unittest.TestCase):\n"
                "    def test_xml_ampersands(self):\n"
                "        from utils import fix_xml_ampersands\n"
                "        self.assertEqual(fix_xml_ampersands('&'), '&amp;')\n",
            )
            result = _find_test_function_using(f, "fix_xml_ampersands", Path(tmp))
            self.assertIn("test_xml_ampersands", result)
            self.assertIn("fix_xml_ampersands", result)

    def test_returns_empty_when_symbol_not_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "test_utils.py"
            self._write(f, "def test_unrelated():\n    assert 1 == 1\n")
            result = _find_test_function_using(f, "fix_xml_ampersands", Path(tmp))
            self.assertEqual(result, "")

    def test_prefers_first_matching_method(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "test_utils.py"
            self._write(
                f,
                "class T(object):\n"
                "    def test_first(self):\n"
                "        use_symbol_here()\n"
                "    def test_second(self):\n"
                "        use_symbol_here()\n",
            )
            result = _find_test_function_using(f, "use_symbol_here", Path(tmp))
            self.assertIn("test_first", result)


if __name__ == "__main__":
    unittest.main()
