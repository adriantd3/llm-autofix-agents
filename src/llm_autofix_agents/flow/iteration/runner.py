from __future__ import annotations

import time
from dataclasses import dataclass, field

from llm_autofix_agents.contracts import RunInput, RunOutput, RunStatus, StopReason, build_run_identity
from llm_autofix_agents.datasets import bugsinpy as _bugsinpy
from llm_autofix_agents.flow.agent_execution import AgentExecutionRunner
from llm_autofix_agents.flow.agent_execution.runner import AgentExecutionContext
from llm_autofix_agents.flow.errors import WorkspaceError
from llm_autofix_agents.flow.execution import tests as _execution_tests
from llm_autofix_agents.flow.execution.tests import to_test_results
from llm_autofix_agents.flow.lifecycle.logs import build_iteration_logs, record_validation_logs
from llm_autofix_agents.flow.lifecycle.output_builder import RunOutputBuilder
from llm_autofix_agents.flow.lifecycle.telemetry_mapping import (
    to_file_change_telemetry_set,
    to_iteration_telemetry_result,
)
from llm_autofix_agents.flow.models import TestExecution, WorkspaceChangeSet
from llm_autofix_agents.flow.policies.iteration import (
    build_continuation_snapshot,
    build_iteration_input,
    proposal_signature,
)
from llm_autofix_agents.flow.policies.stop import StopPolicy
from llm_autofix_agents.flow.policies.validation import (
    IterationValidationResult,
    build_validation_feedback,
    validate_iteration,
)
from llm_autofix_agents.flow.runtime.context import RunConfig, RunState
from llm_autofix_agents.flow.workspace.manager import WorkspaceManager
from llm_autofix_agents.llm.provider import AgentFixIterationRecord
from llm_autofix_agents.observability import utc_now_iso


@dataclass(frozen=True)
class IterationRunner:
    """Coordinates one APR iteration with focused collaborators."""

    agent_runner: AgentExecutionRunner
    workspace: WorkspaceManager
    output_builder: RunOutputBuilder
    stop_policy: StopPolicy = field(default_factory=StopPolicy)

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

        iteration_telemetry = cfg.telemetry.start_iteration(
            iteration_id=identity.iteration_id,
            iteration_index=iteration,
        )
        self.workspace.ensure_temp_branch_for_first_iteration(
            cfg=cfg,
            iteration=iteration,
            logs=state.accumulated_logs,
        )

        before_snapshot = self.workspace.snapshot(cfg)

        state.validation_feedback = None

        # Run the iteration and get the proposed fix from the facade agent
        agent = cfg.facade_agent_builder()
        agent_context = self._build_context(
            run_input=run_input,
            cfg=cfg,
            state=state,
            iteration=iteration,
            identity=identity,
            iteration_telemetry=iteration_telemetry,
            agent=agent,
        )
        iteration_telemetry.record_facade_input(input_text=agent_context.user_input)
        agent_result = self.agent_runner.run_agent(
            context=agent_context,
            execution_index=1,
            provider_call=lambda hooks, event_callback: cfg.provider.run_agent(
                agent=agent,
                user_input=agent_context.user_input,
                max_turns=agent_context.max_turns,
                context=agent_context.agent_context,
                hooks=hooks,
                event_callback=event_callback,
            ),
        )

        changes = self.workspace.inspect_changes(cfg=cfg, before_snapshot=before_snapshot)
        self._write_iteration_patch(cfg=cfg, iteration=iteration, diff=changes.diff)
        self._validate_bugsinpy_workspace(run_input=run_input, cfg=cfg, state=state, phase="iteration")
        test_execution = _execution_tests.run_test_command(
            run_input.test_command,
            cwd=cfg.repo_root,
            timeout_seconds=cfg.test_timeout_seconds,
        )

        iteration_telemetry.record_test_execution(
            phase="iteration_validation",
            command=run_input.test_command,
            exit_code=test_execution.exit_code,
            timed_out=test_execution.timed_out,
            signature=test_execution.signature,
            agent_execution_id=agent_result.agent_execution_id,
        )

        observation = IterationObservation(
            iteration=iteration,
            iteration_id=identity.iteration_id,
            started_at=started_at,
            started_monotonic=started_monotonic,
            proposal=agent_result.proposal,
            agent_execution_id=agent_result.agent_execution_id,
            tool_calls_count=agent_result.tool_calls_count,
            changes=changes,
            test_execution=test_execution,
        )
        self._record_observation(
            iteration_telemetry=iteration_telemetry,
            state=state,
            observation=observation,
        )

        validation = validate_iteration(
            proposal=agent_result.proposal,
            changes=changes,
            current_test_execution=test_execution,
            baseline_test_execution=cfg.baseline_test_execution,
        )
        state.latest_artifacts["validation"] = validation.details
        record_validation_logs(state=state, validation=validation)

        output = self._evaluate_outcome(
            identity=identity,
            run_input=run_input,
            cfg=cfg,
            state=state,
            observation=observation,
            validation=validation,
        )
        if output is not None:
            return output

        self._remember_progress(
            state=state,
            proposal=agent_result.proposal,
            test_signature=test_execution.signature,
        )
        self._append_iteration_logs(
            cfg=cfg,
            state=state,
            iteration=iteration,
            changes=changes,
            test_execution=test_execution,
            confidence=agent_result.proposal.confidence,
        )
        return None

    def _build_context(
        self,
        *,
        run_input: RunInput,
        cfg: RunConfig,
        state: RunState,
        iteration: int,
        identity,
        iteration_telemetry,
        agent,
    ) -> AgentExecutionContext:
        return AgentExecutionContext(
            run_agent_id=cfg.run_agent_id,
            run_agent_ids=cfg.run_agent_ids,
            agent_context=cfg.agent_context,
            iteration_telemetry=iteration_telemetry,
            user_input=build_iteration_input(
                prompt=run_input.prompt,
                iteration=iteration,
                max_iterations=cfg.max_iterations,
                previous_message=state.final_message,
                latest_snapshot=state.latest_snapshot,
                baseline_test_execution=cfg.baseline_test_execution,
                test_command=run_input.test_command,
                validation_feedback=state.validation_feedback,
                repo_root=cfg.repo_root,
            ),
            max_turns=cfg.settings.max_turns,
        )

    def _validate_bugsinpy_workspace(
        self,
        *,
        run_input: RunInput,
        cfg: RunConfig,
        state: RunState,
        phase: str,
    ) -> None:
        if not _bugsinpy.is_bugsinpy_metadata(run_input.metadata):
            return
        compile_required = _bugsinpy.compile_required_from_metadata(run_input.metadata)
        missing = _bugsinpy.missing_workspace_artifacts(cfg.repo_root, compile_required=compile_required)
        if not missing:
            return
        missing_str = ", ".join(missing)
        state.accumulated_logs.append(f"bugsinpy_missing_files={missing_str}")
        raise WorkspaceError(
            f"BugsInPy workspace missing required artifacts before {phase} tests: {missing_str}"
        )

    def _record_observation(
        self,
        *,
        iteration_telemetry,
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

    def _record_state(self, *, state: RunState, observation: IterationObservation) -> None:
        proposal = observation.proposal
        state.total_input_tokens += proposal.input_tokens
        state.total_output_tokens += proposal.output_tokens
        state.total_tokens += proposal.total_tokens
        state.final_message = render_final_message(proposal)
        state.latest_diff = observation.changes.diff
        state.latest_tests = to_test_results(observation.test_execution)
        state.latest_snapshot = build_continuation_snapshot(
            proposal=proposal,
            changes=observation.changes,
            test_execution=observation.test_execution,
        )
        state.max_changed_files_count = max(state.max_changed_files_count, len(observation.changes.all_changed_files))
        proposal.changed_files = list(observation.changes.all_changed_files)

    def _evaluate_outcome(
        self,
        *,
        identity,
        run_input: RunInput,
        cfg: RunConfig,
        state: RunState,
        observation: IterationObservation,
        validation: IterationValidationResult,
    ) -> RunOutput | None:
        proposal = observation.proposal
        test_execution = observation.test_execution
        changed_files = observation.changes.tracked_changed_files

        if not validation.ok:
            if validation.retryable and state.validation_retries < 1:
                self.workspace.restore_all_changes(cfg=cfg, logs=state.accumulated_logs)
                state.validation_feedback = build_validation_feedback(validation)
                state.validation_retries += 1
                self._append_iteration_logs(
                    cfg=cfg,
                    state=state,
                    iteration=observation.iteration,
                    changes=observation.changes,
                    test_execution=test_execution,
                    confidence=proposal.confidence,
                )
                state.accumulated_logs.append(f"validation_result={validation.failure_type}_retryable")
                return None
            self._append_iteration_logs(
                cfg=cfg,
                state=state,
                iteration=observation.iteration,
                changes=observation.changes,
                test_execution=test_execution,
                confidence=proposal.confidence,
            )
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
            proposal=proposal,
            test_execution=test_execution,
            changed_files=changed_files,
        ):
            self._append_iteration_logs(
                cfg=cfg,
                state=state,
                iteration=observation.iteration,
                changes=observation.changes,
                test_execution=test_execution,
                confidence=proposal.confidence,
            )
            self.workspace.restore_temp_branch_for_debug(cfg=cfg, logs=state.accumulated_logs)
            return self.output_builder.build(
                identity=identity,
                status=RunStatus.PARTIAL,
                stop_reason=StopReason.NO_PROGRESS,
                state=state,
                cfg=cfg,
            )

        if self.stop_policy.success(
            run_input=run_input,
            proposal=proposal,
            test_execution=test_execution,
            changed_files=changed_files,
        ):
            self._append_iteration_logs(
                cfg=cfg,
                state=state,
                iteration=observation.iteration,
                changes=observation.changes,
                test_execution=test_execution,
                confidence=proposal.confidence,
            )
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

        if self.stop_policy.agent_reported_stuck(proposal):
            self._append_iteration_logs(
                cfg=cfg,
                state=state,
                iteration=observation.iteration,
                changes=observation.changes,
                test_execution=test_execution,
                confidence=proposal.confidence,
            )
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

    def _write_iteration_patch(self, *, cfg: RunConfig, iteration: int, diff: str) -> None:
        patch_path = cfg.results_dir / f"it{iteration}.patch"
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.write_text(diff, encoding="utf-8")

    def _remember_progress(self, *, state: RunState, proposal: AgentFixIterationRecord, test_signature: str) -> None:
        state.previous_proposal_signature = proposal_signature(proposal)
        state.previous_proposal_status = proposal.status
        state.previous_proposal_confidence = proposal.confidence
        state.previous_test_signature = test_signature

    def _append_iteration_logs(
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


def render_final_message(proposal: AgentFixIterationRecord) -> str:
    files = ", ".join(proposal.changed_files) if proposal.changed_files else "(unspecified)"
    lines = [
        f"status: {proposal.status}",
        f"reasoning_summary: {proposal.reasoning_summary}",
        f"confidence: {proposal.confidence:.3f}",
        f"changed_files: {files}",
    ]
    return "\n".join(lines)
