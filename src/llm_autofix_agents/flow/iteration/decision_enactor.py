from __future__ import annotations

from dataclasses import dataclass

from llm_autofix_agents.contracts import RunIdentity, RunInput, RunOutput, RunStatus, StopReason
from llm_autofix_agents.flow.lifecycle.logs import build_iteration_logs
from llm_autofix_agents.flow.lifecycle.output_builder import RunOutputBuilder
from llm_autofix_agents.flow.models import IterationDecision, IterationObservation
from llm_autofix_agents.flow.policies.iteration import proposal_signature
from llm_autofix_agents.flow.policies.validation import IterationValidationResult, build_validation_feedback
from llm_autofix_agents.flow.runtime.context import RunConfig, RunState
from llm_autofix_agents.flow.workspace.manager import WorkspaceManager


@dataclass(frozen=True)
class IterationDecisionEnactor:
    """Applies the effects of an iteration decision: workspace cleanup, state mutations, output building.

    Owns the effect-producing dependencies (workspace, output_builder) so that
    IterationRunner is a pure sequencer and does not encode what each decision action means.
    """

    workspace: WorkspaceManager
    output_builder: RunOutputBuilder

    def enact(
        self,
        *,
        decision: IterationDecision,
        identity: RunIdentity,
        run_input: RunInput,
        cfg: RunConfig,
        state: RunState,
        observation: IterationObservation,
        validation: IterationValidationResult,
    ) -> RunOutput | None:
        if decision.action == "retry":
            self.workspace.restore_all_changes(
                repo_root=cfg.repo_root,
                logs=state.accumulated_logs,
            )
            state.validation_feedback = build_validation_feedback(validation)
            state.validation_retries += 1
            self._append_iteration_logs(cfg=cfg, state=state, observation=observation)
            if decision.log_suffix:
                state.accumulated_logs.append(decision.log_suffix)
            return None

        if decision.action == "stop_validation_failure":
            self._append_iteration_logs(cfg=cfg, state=state, observation=observation)
            self.workspace.restore_temp_branch_for_debug(
                repo_root=cfg.repo_root,
                temp_branch=state.temp_branch,
                logs=state.accumulated_logs,
            )
            if decision.log_suffix:
                state.accumulated_logs.append(decision.log_suffix)
            return self.output_builder.validation_failure(
                identity=identity,
                validation=validation,
                state=state,
            )

        if decision.action == "stop_no_progress":
            self._append_iteration_logs(cfg=cfg, state=state, observation=observation)
            self.workspace.restore_temp_branch_for_debug(
                repo_root=cfg.repo_root,
                temp_branch=state.temp_branch,
                logs=state.accumulated_logs,
            )
            return self.output_builder.build(
                identity=identity,
                status=RunStatus.PARTIAL,
                stop_reason=StopReason.NO_PROGRESS,
                state=state,
            )

        if decision.action == "stop_success":
            self._append_iteration_logs(cfg=cfg, state=state, observation=observation)
            cleanup_error = self.workspace.cleanup_temp_branch_after_success(
                repo_root=cfg.repo_root,
                temp_branch=state.temp_branch,
            )
            if cleanup_error:
                return self.output_builder.branch_cleanup_failed(
                    identity=identity,
                    state=state,
                    cleanup_error=cleanup_error,
                )
            return self.output_builder.build(
                identity=identity,
                status=RunStatus.SUCCESS,
                stop_reason=StopReason.COMPLETED,
                state=state,
            )

        if decision.action == "stop_agent_stuck":
            self._append_iteration_logs(cfg=cfg, state=state, observation=observation)
            self.workspace.restore_temp_branch_for_debug(
                repo_root=cfg.repo_root,
                temp_branch=state.temp_branch,
                logs=state.accumulated_logs,
            )
            if decision.log_suffix:
                state.accumulated_logs.append(decision.log_suffix)
            return self.output_builder.build(
                identity=identity,
                status=RunStatus.PARTIAL,
                stop_reason=StopReason.NO_PROGRESS,
                state=state,
            )

        # action == "continue"
        self._remember_progress(state=state, observation=observation)
        self._append_iteration_logs(cfg=cfg, state=state, observation=observation)
        return None

    def _append_iteration_logs(
        self,
        *,
        cfg: RunConfig,
        state: RunState,
        observation: IterationObservation,
    ) -> None:
        state.accumulated_logs.extend(
            build_iteration_logs(
                architecture_name=cfg.architecture_name,
                iteration=observation.iteration,
                max_iterations=cfg.max_iterations,
                changed_files=observation.changes.all_changed_files,
                test_execution=observation.test_execution,
                confidence=observation.proposal.confidence,
                tool_profile=cfg.tool_profile,
                tool_count=cfg.tool_count,
                provider=cfg.settings.provider.value,
                model=cfg.settings.model,
            )
        )

    def _remember_progress(self, *, state: RunState, observation: IterationObservation) -> None:
        proposal = observation.proposal
        state.previous_proposal_signature = proposal_signature(proposal)
        state.previous_proposal_status = proposal.status
        state.previous_proposal_confidence = proposal.confidence
        state.previous_test_signature = observation.test_execution.signature
