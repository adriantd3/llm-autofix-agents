from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from llm_autofix_agents.contracts import ErrorCategory, RunError
from llm_autofix_agents.flow.models import TestExecution, WorkspaceChangeSet
from llm_autofix_agents.flow.policies.iteration import is_regression
from llm_autofix_agents.llm.provider import AgentFixIterationRecord


@dataclass(frozen=True)
class IterationValidationResult:
    """Validation outcome based on runtime-observed facts."""

    ok: bool
    failure_type: str | None = None
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_errors(self) -> list[RunError]:
        if self.ok:
            return []

        return [
            RunError(
                category=ErrorCategory.VALIDATION,
                message=_validation_message(self.failure_type),
                retryable=False,
                details=self.details,
            )
        ]


def validate_iteration(
    *,
    proposal: AgentFixIterationRecord,
    changes: WorkspaceChangeSet,
    current_test_execution: TestExecution,
    baseline_test_execution: TestExecution | None,
) -> IterationValidationResult:
    tracked_files = _normalize_paths(changes.tracked_changed_files)
    observed_files = _normalize_paths(changes.all_changed_files)
    untracked_files = _normalize_paths(changes.untracked_files)

    details: dict[str, Any] = {
        "observed_changed_files": observed_files,
        "observed_tracked_changed_files": tracked_files,
        "observed_untracked_files": untracked_files,
        "diff_excludes_untracked": changes.diff_excludes_untracked,
        "untracked_files_policy": "allowed_and_captured",
    }

    if changes.repo_changed and not changes.diff.strip() and not changes.added_files:
        return IterationValidationResult(
            ok=False,
            failure_type="diff_integrity",
            details={
                **details,
                "reason": "Snapshot detected changed files, but git diff is empty after filtering.",
            },
        )

    changed_test_files = [f for f in observed_files if _is_test_file(f)]
    if changed_test_files:
        return IterationValidationResult(
            ok=False,
            failure_type="test_file_modified",
            retryable=True,
            details={
                **details,
                "reason": "Agent modified test files, which is forbidden. The failing tests are correct.",
                "changed_test_files": changed_test_files,
            },
        )

    if baseline_test_execution and is_regression(baseline=baseline_test_execution, current=current_test_execution):
        return IterationValidationResult(
            ok=False,
            failure_type="regression",
            details={
                **details,
                "baseline_exit_code": baseline_test_execution.exit_code,
                "current_exit_code": current_test_execution.exit_code,
                "baseline_signature": baseline_test_execution.signature,
                "current_signature": current_test_execution.signature,
            },
        )

    return IterationValidationResult(ok=True, details=details)


def _validation_message(failure_type: str | None) -> str:
    return {
        "diff_integrity": "Diff integrity validation failed",
        "regression": "Regression detected against baseline test execution",
        "test_file_modified": "Agent modified test files, which is forbidden",
    }.get(failure_type or "", "Validation failed")


def build_validation_feedback(validation: IterationValidationResult) -> str:
    """Build a human-readable feedback message for a retryable validation failure."""
    if validation.failure_type == "test_file_modified":
        files = validation.details.get("changed_test_files", [])
        files_str = ", ".join(files) if files else "(unknown)"
        return (
            f"You modified test files ({files_str}), which is FORBIDDEN. "
            f"The failing tests are CORRECT — the bug is in the source code, not the tests. "
            f"Your changes have been reverted. Fix ONLY source code files."
        )
    return validation.details.get("reason", "Validation failed")


def _normalize_paths(paths: list[str]) -> list[str]:
    return sorted(path.replace("\\", "/") for path in paths)


def _is_test_file(path: str) -> bool:
    """Return True if the path looks like a test file.

    Catches: test/, tests/ roots; any directory named test or tests anywhere
    in the path (e.g. tqdm/tests/); filenames starting with test_ or tests_,
    or ending with _test (e.g. tests_contrib.py, foo_test.py).
    """
    lowered = path.lower().replace("\\", "/")
    if lowered.startswith("test/") or lowered.startswith("tests/"):
        return True
    parts = lowered.split("/")
    for part in parts:
        stem = part.rsplit(".", 1)[0] if "." in part else part
        if stem in ("test", "tests"):
            return True
        if stem.startswith("test_") or stem.startswith("tests_") or stem.endswith("_test"):
            return True
    return False
