from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from llm_autofix_agents.llm.provider import AgentFixIterationRecord


@dataclass(frozen=True)
class TestExecution:
    exit_code: int
    timed_out: bool
    output: str
    signature: str


@dataclass(frozen=True)
class PatchApplyResult:
    applied: bool
    reason: str


@dataclass(frozen=True)
class WorkspaceChangeSet:
    """Authoritative repository changes observed by the runtime."""

    modified_files: list[str]
    added_files: list[str]
    deleted_files: list[str]
    untracked_files: list[str]
    diff: str
    diff_excludes_untracked: bool

    @property
    def tracked_changed_files(self) -> list[str]:
        return sorted({*self.modified_files, *self.added_files, *self.deleted_files})

    @property
    def all_changed_files(self) -> list[str]:
        return sorted({*self.tracked_changed_files, *self.untracked_files})

    @property
    def repo_changed(self) -> bool:
        return bool(self.all_changed_files)


@dataclass(frozen=True)
class IterationObservation:
    """Observed results of a single APR iteration."""

    iteration: int
    iteration_id: str
    started_at: str
    started_monotonic: float
    proposal: AgentFixIterationRecord
    agent_execution_id: str
    tool_calls_count: int
    changes: WorkspaceChangeSet
    test_execution: TestExecution


def render_final_message(proposal: AgentFixIterationRecord, *, observed_files: list[str]) -> str:
    files = ", ".join(observed_files) if observed_files else "(none observed)"
    lines = [
        f"status: {proposal.status}",
        f"reasoning_summary: {proposal.reasoning_summary}",
        f"confidence: {proposal.confidence:.3f}",
        f"changed_files: {files}",
    ]
    return "\n".join(lines)


@dataclass(frozen=True)
class IterationDecision:
    """Pure outcome of evaluating an iteration — no side effects.

    Actions:
    - "continue": iteration was not terminal, proceed to next
    - "retry": validation failed but is retryable, revert and retry same iteration
    - "stop_success": tests pass and files changed
    - "stop_no_progress": agent is stuck or no progress detected
    - "stop_validation_failure": non-retryable validation failure
    - "stop_agent_stuck": agent explicitly reported stuck
    """

    action: Literal[
        "continue",
        "retry",
        "stop_success",
        "stop_no_progress",
        "stop_validation_failure",
        "stop_agent_stuck",
    ]
    log_suffix: str | None = None
