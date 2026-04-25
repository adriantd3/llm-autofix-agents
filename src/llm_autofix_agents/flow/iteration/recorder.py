from __future__ import annotations

import time
from dataclasses import dataclass

from llm_autofix_agents.flow.lifecycle.logs import build_iteration_logs
from llm_autofix_agents.flow.models import TestExecution, WorkspaceChangeSet
from llm_autofix_agents.flow.policies.iteration import proposal_signature
from llm_autofix_agents.flow.runtime.context import RunConfig, RunState
from llm_autofix_agents.llm.provider import AgentFixIterationRecord


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

    def record(self, *, cfg: RunConfig, state: RunState, observation: IterationObservation) -> None:
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

        cfg.telemetry.record_file_changes(
            run_id=cfg.run_id,
            iteration=observation.iteration,
            iteration_id=observation.iteration_id,
            agent_execution_id=observation.agent_execution_id,
            changed_files=observation.changes.all_changed_files,
        )
        cfg.telemetry.finish_iteration(
            run_id=cfg.run_id,
            iteration_id=observation.iteration_id,
            iteration_index=observation.iteration,
            started_at=observation.started_at,
            status=proposal.status,
            duration_seconds=max(0.0, time.perf_counter() - observation.started_monotonic),
            input_tokens=proposal.input_tokens,
            output_tokens=proposal.output_tokens,
            total_tokens=proposal.total_tokens,
            tool_calls_count=observation.tool_calls_count,
            changed_files_count=len(observation.changes.all_changed_files),
            repo_changed=observation.changes.repo_changed,
            test_exit_code=observation.test_execution.exit_code,
            test_timed_out=observation.test_execution.timed_out,
            test_signature=observation.test_execution.signature,
        )

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
