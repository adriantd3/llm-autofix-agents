from __future__ import annotations

from dataclasses import dataclass

from llm_autofix_agents.contracts import RunIdentity, RunInput, RunOutput, RunStatus, StopReason
from llm_autofix_agents.flow.iteration.recorder import IterationObservation
from llm_autofix_agents.flow.lifecycle.output_builder import RunOutputBuilder
from llm_autofix_agents.flow.policies.stop import StopPolicy
from llm_autofix_agents.flow.policies.validation import IterationValidationResult
from llm_autofix_agents.flow.runtime.context import RunConfig, RunState
from llm_autofix_agents.flow.workspace.manager import WorkspaceManager


@dataclass(frozen=True)
class IterationOutcomeHandler:
    """Decides terminal run outputs from iteration outcomes."""

    workspace: WorkspaceManager
    output_builder: RunOutputBuilder
    stop_policy: StopPolicy

    def evaluate(
        self,
        *,
        identity: RunIdentity,
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

        if self.stop_policy.agent_reported_stuck(proposal):
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
