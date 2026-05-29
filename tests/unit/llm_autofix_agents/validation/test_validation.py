from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from llm_autofix_agents.validation.canonical import resolve_canonical_patch
from llm_autofix_agents.validation.models import RunValidationInput, ValidatorOutput
from llm_autofix_agents.validation.prompt import build_validator_prompt, get_system_prompt


class TestResolveCanonicalPatch(unittest.TestCase):
    def test_returns_none_when_no_root(self) -> None:
        result = resolve_canonical_patch(dataset_type="quixbugs", problem_id="gcd", canonical_root=None)
        self.assertIsNone(result)

    def test_quixbugs_reads_correct_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prog_dir = root / "correct_python_programs"
            prog_dir.mkdir()
            (prog_dir / "gcd.py").write_text("def gcd(a, b):\n    return a if b == 0 else gcd(b, a % b)\n")

            result = resolve_canonical_patch(dataset_type="quixbugs", problem_id="gcd", canonical_root=root)

        self.assertIsNotNone(result)
        self.assertIn("gcd", result)

    def test_bugsinpy_reads_patch_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bug_dir = root / "projects" / "youtube-dl" / "bugs" / "1"
            bug_dir.mkdir(parents=True)
            (bug_dir / "bug_patch.txt").write_text("--- a/ydl.py\n+++ b/ydl.py\n")

            result = resolve_canonical_patch(
                dataset_type="bugsinpy", problem_id="youtube-dl-1", canonical_root=root
            )

        self.assertIsNotNone(result)
        self.assertIn("ydl.py", result)

    def test_returns_none_when_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = resolve_canonical_patch(
                dataset_type="quixbugs", problem_id="nonexistent", canonical_root=Path(tmp)
            )
        self.assertIsNone(result)

    def test_unknown_dataset_type_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = resolve_canonical_patch(
                dataset_type="unknown_dataset", problem_id="foo", canonical_root=Path(tmp)
            )
        self.assertIsNone(result)


class TestBuildValidatorPrompt(unittest.TestCase):
    def _make_ctx(
        self,
        generated_patch: str | None = "--- a/gcd.py\n+++ b/gcd.py\n-    return a\n+    return a if b == 0 else gcd(b, a % b)",
        canonical_patch: str | None = "def gcd(a, b): return a if b == 0 else gcd(b, a % b)",
        test_output: str | None = "PASSED 5 tests",
        test_exit_code: int | None = 0,
    ) -> RunValidationInput:
        return RunValidationInput(
            run_id="run-001",
            problem_id="gcd",
            benchmark_name="quixbugs",
            dataset_type="quixbugs",
            test_exit_code=test_exit_code,
            generated_patch=generated_patch,
            canonical_patch=canonical_patch,
            test_output=test_output,
        )

    def test_prompt_contains_run_id(self) -> None:
        prompt = build_validator_prompt(self._make_ctx())
        self.assertIn("run-001", prompt)

    def test_prompt_contains_bug_id(self) -> None:
        prompt = build_validator_prompt(self._make_ctx())
        self.assertIn("gcd", prompt)

    def test_prompt_contains_generated_patch(self) -> None:
        prompt = build_validator_prompt(self._make_ctx())
        self.assertIn("Generated patch", prompt)

    def test_prompt_contains_canonical_patch(self) -> None:
        prompt = build_validator_prompt(self._make_ctx())
        self.assertIn("Canonical patch", prompt)
        self.assertIn("gcd(b, a % b)", prompt)

    def test_prompt_notes_missing_generated_patch(self) -> None:
        prompt = build_validator_prompt(self._make_ctx(generated_patch=None))
        self.assertIn("NOT AVAILABLE", prompt)

    def test_prompt_notes_missing_canonical_patch(self) -> None:
        prompt = build_validator_prompt(self._make_ctx(canonical_patch=None))
        self.assertIn("NOT AVAILABLE", prompt)

    def test_system_prompt_contains_protocol_keywords(self) -> None:
        sys_prompt = get_system_prompt()
        for keyword in ("CORRECT", "PLAUSIBLE", "OVERFITTING", "PROTOCOL"):
            self.assertIn(keyword, sys_prompt)


class TestValidatorOutputModel(unittest.TestCase):
    def test_valid_output_parses(self) -> None:
        output = ValidatorOutput(
            verdict="CORRECT",
            confidence=0.95,
            test_passed=True,
            patch_semantically_matches=True,
            justification="Fix addresses root cause.",
        )
        self.assertEqual(output.verdict, "CORRECT")
        self.assertAlmostEqual(output.confidence, 0.95)

    def test_confidence_bounds_enforced(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            ValidatorOutput(
                verdict="CORRECT",
                confidence=1.5,  # out of range
                test_passed=True,
                justification="x",
            )

    def test_patch_semantically_matches_nullable(self) -> None:
        output = ValidatorOutput(
            verdict="FAIL",
            confidence=0.0,
            test_passed=False,
            justification="No passing patch was available.",
        )
        self.assertIsNone(output.patch_semantically_matches)


if __name__ == "__main__":
    unittest.main()
