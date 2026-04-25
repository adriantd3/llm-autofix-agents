from __future__ import annotations

from dataclasses import dataclass

from llm_autofix_agents.flow.lifecycle.logs import build_iteration_logs
from llm_autofix_agents.flow.lifecycle.telemetry_mapping import (
    to_file_change_telemetry_set,
    to_iteration_telemetry_result,
)
from llm_autofix_agents.flow.models import TestExecution, WorkspaceChangeSet
from llm_autofix_agents.flow.policies.iteration import proposal_signature
from llm_autofix_agents.flow.runtime.context import RunConfig, RunState
from llm_autofix_agents.llm.provider import AgentFixIterationRecord
from llm_autofix_agents.observability.telemetry import IterationTelemetry


@dataclass(frozen=True)
class IterationObservation:
    iteration: int
    iteration_id: str
    started_at: str
    started_monotonic: float
    proposal: AgentFixIterationRecord
    agent_execution_id: str
    tool_calls_count: int
    changes: WorkspaceChangeSet
    test_execution: TestExecution


@dataclass(frozen=True)
class IterationRecorder:
    """Records observed iteration facts into state and observability."""

    def record(
        self,
        *,
        iteration_telemetry: IterationTelemetry,
        state: RunState,
        observation: IterationObservation,
    ) -> None:
        self._record_state(state=state, observation=observation)

        iteration_telemetry.record_file_changes(
            agent_execution_id=observation.agent_execution_id,
            changes=to_file_change_telemetry_set(observation.changes),
        )

        iteration_telemetry.finish_iteration(
            result=to_iteration_telemetry_result(observation),
        )

    def _record_state(
        self,
        *,
        state: RunState,
        observation: IterationObservation,
    ) -> None:
        proposal = observation.proposal
        state.total_input_tokens += proposal.input_tokens
        state.total_output_tokens += proposal.output_tokens
        state.total_tokens += proposal.total_tokens
        state.final_message = render_final_message(proposal)
        state.latest_diff = observation.changes.diff
        state.latest_changed_files = list(observation.changes.all_changed_files)
        state.latest_proposal_changed_files = list(proposal.changed_files)
        state.latest_tests = _to_test_results(observation.test_execution)
        state.max_changed_files_count = max(state.max_changed_files_count, len(observation.changes.all_changed_files))

    def remember_progress(self, *, state: RunState, proposal: AgentFixIterationRecord, test_signature: str) -> None:
        state.previous_proposal_signature = proposal_signature(proposal)
        state.previous_proposal_status = proposal.status
        state.previous_proposal_confidence = proposal.confidence
        state.previous_test_signature = test_signature

    def append_iteration_logs(
        self,
        *,
        cfg: RunConfig,
        state: RunState,
        iteration: int,
        changes: WorkspaceChangeSet,
        test_execution: TestExecution,
        confidence: float,
    ) -> None:
        state.accumulated_logs.extend(
            build_iteration_logs(
                cfg=cfg,
                iteration=iteration,
                changed_files=changes.all_changed_files,
                test_execution=test_execution,
                confidence=confidence,
            )
        )


def render_final_message(proposal: AgentFixIterationRecord) -> str:
    files = ", ".join(proposal.changed_files) if proposal.changed_files else "(unspecified)"
    lines = [
        f"status: {proposal.status}",
        f"reasoning_summary: {proposal.reasoning_summary}",
        f"confidence: {proposal.confidence:.3f}",
        f"changed_files: {files}",
    ]
    if proposal.notes:
        lines.append(f"notes: {proposal.notes}")
    return "\n".join(lines)


def _to_test_results(execution: TestExecution):
    from llm_autofix_agents.flow.execution.tests import to_test_results

    return to_test_results(execution)
