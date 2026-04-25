from __future__ import annotations

import time
from dataclasses import dataclass

from llm_autofix_agents.contracts import RunInput, RunOutput, RunStatus, StopReason, build_run_identity
from llm_autofix_agents.flow.architecture import AgentIterationContext, ArchitectureRunner
from llm_autofix_agents.flow.execution.tests import run_test_command, to_test_results
from llm_autofix_agents.flow.lifecycle.events import IterationEvents
from llm_autofix_agents.flow.lifecycle.logs import build_iteration_logs, record_validation_logs
from llm_autofix_agents.flow.lifecycle.output_builder import RunOutputBuilder
from llm_autofix_agents.flow.policies.iteration import build_iteration_input, proposal_signature
from llm_autofix_agents.flow.policies.stop import StopPolicy
from llm_autofix_agents.flow.policies.validation import validate_iteration
from llm_autofix_agents.flow.runtime.context import RunConfig, RunState
from llm_autofix_agents.flow.workspace.manager import WorkspaceManager
from llm_autofix_agents.llm.provider import AgentFixIterationRecord
from llm_autofix_agents.observability import utc_now_iso


@dataclass(frozen=True)
class IterationRunner:
    """Coordinates one APR iteration.

    The runner owns iteration-local sequencing. Low-level record creation and workspace
    mechanics remain delegated.
    """

    architecture: ArchitectureRunner
    workspace: WorkspaceManager
    events: IterationEvents
    output_builder: RunOutputBuilder
    stop_policy: StopPolicy = StopPolicy()

    def run(
        self,
        *,
        run_input: RunInput,
        cfg: RunConfig,
        state: RunState,
        iteration: int,
    ) -> RunOutput | None:
        identity = build_run_identity(
            run_input=run_input,
            agent_config=cfg.agent_config,
            iteration=iteration,
            run_id=cfg.run_id,
        )
        started_at = utc_now_iso()
        started_monotonic = time.perf_counter()

        self.events.started(cfg=cfg, iteration_id=identity.iteration_id, iteration_index=iteration)
        self.workspace.ensure_temp_branch_for_first_iteration(
            cfg=cfg,
            iteration=iteration,
            logs=state.accumulated_logs,
        )

        before_snapshot = self.workspace.snapshot(cfg)
        agent_result = self.architecture.run_iteration(
            AgentIterationContext(
                run_id=cfg.run_id,
                iteration_id=identity.iteration_id,
                iteration_index=iteration,
                run_agent_id=cfg.run_agent_id,
                run_input=run_input,
                settings=cfg.settings,
                provider=cfg.provider,
                agent_context=cfg.agent_context,
                agent_tools=cfg.agent_tools,
                observer=cfg.observer,
                user_input=build_iteration_input(
                    prompt=run_input.prompt,
                    iteration=iteration,
                    max_iterations=cfg.max_iterations,
                    previous_message=state.final_message,
                ),
                max_turns=cfg.settings.max_turns,
            )
        )

        changes = self.workspace.inspect_changes(cfg=cfg, before_snapshot=before_snapshot)
        test_execution = run_test_command(
            run_input.test_command,
            cwd=cfg.repo_root,
            timeout_seconds=cfg.test_timeout_seconds,
        )

        self.events.test_execution(
            observer=cfg.observer,
            run_id=cfg.run_id,
            phase="iteration_validation",
            test_execution=test_execution,
            command=run_input.test_command,
            iteration=iteration,
            iteration_id=identity.iteration_id,
            agent_execution_id=agent_result.agent_execution_id,
        )

        self._record_observed_iteration(
            cfg=cfg,
            state=state,
            iteration=iteration,
            iteration_id=identity.iteration_id,
            started_at=started_at,
            started_monotonic=started_monotonic,
            proposal=agent_result.proposal,
            agent_execution_id=agent_result.agent_execution_id,
            tool_calls_count=agent_result.tool_calls_count,
            changed_files=changes.changed_files,
            diff=changes.diff,
            test_execution=test_execution,
        )

        validation = validate_iteration(
            proposal=agent_result.proposal,
            observed_changed_files=changes.changed_files,
            diff=changes.diff,
            current_test_execution=test_execution,
            baseline_test_execution=cfg.baseline_test_execution,
        )
        state.latest_artifacts["validation"] = validation.details
        record_validation_logs(state=state, validation=validation)

        if not validation.ok:
            self.workspace.restore_temp_branch_for_debug(cfg=cfg, logs=state.accumulated_logs)
            state.accumulated_logs.append(f"validation_result={validation.failure_type}")
            return self.output_builder.validation_failure(
                identity=identity,
                validation=validation,
                state=state,
                cfg=cfg,
            )

        if self.stop_policy.no_progress(
            state=state,
            proposal=agent_result.proposal,
            test_execution=test_execution,
            changed_files=changes.changed_files,
        ):
            self.workspace.restore_temp_branch_for_debug(cfg=cfg, logs=state.accumulated_logs)
            return self.output_builder.build(
                identity=identity,
                status=RunStatus.PARTIAL,
                stop_reason=StopReason.NO_PROGRESS,
                state=state,
                cfg=cfg,
            )

        self._remember_progress_state(state=state, proposal=agent_result.proposal, test_signature=test_execution.signature)
        state.accumulated_logs.extend(
            build_iteration_logs(
                cfg=cfg,
                iteration=iteration,
                changed_files=changes.changed_files,
                test_execution=test_execution,
                confidence=agent_result.proposal.confidence,
            )
        )

        if self.stop_policy.success(
            run_input=run_input,
            proposal=agent_result.proposal,
            test_execution=test_execution,
        ):
            cleanup_error = self.workspace.cleanup_temp_branch_after_success(cfg)
            if cleanup_error:
                return self.output_builder.branch_cleanup_failed(
                    identity=identity,
                    state=state,
                    cfg=cfg,
                    cleanup_error=cleanup_error,
                )
            return self.output_builder.build(
                identity=identity,
                status=RunStatus.SUCCESS,
                stop_reason=StopReason.COMPLETED,
                state=state,
                cfg=cfg,
            )

        if self.stop_policy.agent_reported_stuck(agent_result.proposal):
            self.workspace.restore_temp_branch_for_debug(cfg=cfg, logs=state.accumulated_logs)
            state.accumulated_logs.append("iteration_result=agent_reported_stuck")
            return self.output_builder.build(
                identity=identity,
                status=RunStatus.PARTIAL,
                stop_reason=StopReason.NO_PROGRESS,
                state=state,
                cfg=cfg,
            )

        return None

    def _record_observed_iteration(
        self,
        *,
        cfg: RunConfig,
        state: RunState,
        iteration: int,
        iteration_id: str,
        started_at: str,
        started_monotonic: float,
        proposal: AgentFixIterationRecord,
        agent_execution_id: str,
        tool_calls_count: int,
        changed_files: list[str],
        diff: str,
        test_execution,
    ) -> None:
        state.total_input_tokens += proposal.input_tokens
        state.total_output_tokens += proposal.output_tokens
        state.total_tokens += proposal.total_tokens
        state.final_message = _render_final_message(proposal)
        state.latest_diff = diff
        state.latest_changed_files = changed_files
        state.latest_proposal_changed_files = list(proposal.changed_files)
        state.latest_tests = to_test_results(test_execution)
        state.max_changed_files_count = max(state.max_changed_files_count, len(changed_files))

        self.events.file_changes(
            cfg=cfg,
            iteration=iteration,
            iteration_id=iteration_id,
            agent_execution_id=agent_execution_id,
            changed_files=changed_files,
        )
        self.events.finished(
            cfg=cfg,
            iteration_id=iteration_id,
            iteration_index=iteration,
            started_at=started_at,
            proposal=proposal,
            duration_seconds=max(0.0, time.perf_counter() - started_monotonic),
            tool_calls_count=tool_calls_count,
            changed_files_count=len(changed_files),
            repo_changed=bool(changed_files),
            test_execution=test_execution,
        )

    def _remember_progress_state(
        self,
        *,
        state: RunState,
        proposal: AgentFixIterationRecord,
        test_signature: str,
    ) -> None:
        state.previous_proposal_signature = proposal_signature(proposal)
        state.previous_proposal_status = proposal.status
        state.previous_proposal_confidence = proposal.confidence
        state.previous_test_signature = test_signature


def _render_final_message(proposal: AgentFixIterationRecord) -> str:
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
