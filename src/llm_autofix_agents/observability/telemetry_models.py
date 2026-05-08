from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llm_autofix_agents.flow.models import IterationObservation, WorkspaceChangeSet


@dataclass(frozen=True)
class FileChangeTelemetrySet:
    """Semantic file change set for telemetry."""

    modified_files: list[str]
    added_files: list[str]
    deleted_files: list[str]
    untracked_files: list[str]

    @classmethod
    def from_workspace_changes(cls, changes: WorkspaceChangeSet) -> FileChangeTelemetrySet:
        return cls(
            modified_files=list(changes.modified_files),
            added_files=list(changes.added_files),
            deleted_files=list(changes.deleted_files),
            untracked_files=list(changes.untracked_files),
        )


@dataclass(frozen=True)
class IterationTelemetryResult:
    """Complete result for finishing an iteration."""

    started_at: str
    duration_seconds: float
    status: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    tool_calls_count: int
    changed_files_count: int
    repo_changed: bool
    test_exit_code: int
    test_timed_out: bool
    test_signature: str

    @classmethod
    def from_observation(cls, observation: IterationObservation) -> IterationTelemetryResult:
        proposal = observation.proposal
        test_execution = observation.test_execution
        return cls(
            started_at=observation.started_at,
            duration_seconds=max(0.0, time.perf_counter() - observation.started_monotonic),
            status=proposal.status,
            input_tokens=proposal.input_tokens,
            output_tokens=proposal.output_tokens,
            total_tokens=proposal.total_tokens,
            tool_calls_count=observation.tool_calls_count,
            changed_files_count=len(observation.changes.all_changed_files),
            repo_changed=observation.changes.repo_changed,
            test_exit_code=test_execution.exit_code,
            test_timed_out=test_execution.timed_out,
            test_signature=test_execution.signature,
        )
