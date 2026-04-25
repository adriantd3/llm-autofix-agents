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
    proposal_files = _normalize_paths(proposal.changed_files)
    observed_files = _normalize_paths(changes.changed_files)
    untracked_files = _normalize_paths(changes.untracked_files)

    details: dict[str, Any] = {
        "proposal_changed_files": proposal_files,
        "observed_changed_files": observed_files,
        "observed_untracked_files": untracked_files,
        "proposal_matches_observed_files": proposal_files == observed_files,
        "diff_complete": changes.diff_complete,
    }

    if changes.repo_changed and not changes.diff.strip() and changes.diff_complete:
        return IterationValidationResult(
            ok=False,
            failure_type="diff_integrity",
            details={
                **details,
                "reason": "Snapshot detected changed files, but git diff is empty after filtering.",
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
    }.get(failure_type or "", "Validation failed")


def _normalize_paths(paths: list[str]) -> list[str]:
    return sorted(path.replace("\\", "/") for path in paths)
