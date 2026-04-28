from __future__ import annotations

import time
from typing import TYPE_CHECKING

from llm_autofix_agents.flow.models import WorkspaceChangeSet
from llm_autofix_agents.observability.telemetry_models import (
    FileChangeTelemetrySet,
    IterationTelemetryResult,
)

if TYPE_CHECKING:
    from llm_autofix_agents.flow.iteration.runner import IterationObservation


def to_file_change_telemetry_set(changes: WorkspaceChangeSet) -> FileChangeTelemetrySet:
    """Convert a WorkspaceChangeSet into a categorized FileChangeTelemetrySet."""
    return FileChangeTelemetrySet(
        modified_files=list(changes.modified_files),
        added_files=list(changes.added_files),
        deleted_files=list(changes.deleted_files),
        untracked_files=list(changes.untracked_files),
    )


def to_iteration_telemetry_result(
    observation: IterationObservation,
) -> IterationTelemetryResult:
    """Convert an IterationObservation into an IterationTelemetryResult."""
    proposal = observation.proposal
    test_execution = observation.test_execution

    return IterationTelemetryResult(
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
