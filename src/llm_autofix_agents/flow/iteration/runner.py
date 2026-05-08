from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from llm_autofix_agents.contracts import RunIdentity, RunInput, RunOutput, RunStatus, StopReason, build_run_identity
from llm_autofix_agents.flow.agent_execution import AgentExecutionRunner
from llm_autofix_agents.flow.agent_execution.runner import AgentExecutionContext, AgentExecutionResult
from llm_autofix_agents.flow.execution import run_test_command, to_test_results
from llm_autofix_agents.flow.lifecycle.logs import build_iteration_logs, record_validation_logs
from llm_autofix_agents.flow.lifecycle.output_builder import RunOutputBuilder
from llm_autofix_agents.flow.models import (
    IterationDecision,
    IterationObservation,
    render_final_message,
)
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
from llm_autofix_agents.observability.telemetry import IterationTelemetry
from llm_autofix_agents.observability.telemetry_models import (
    FileChangeTelemetrySet,
    IterationTelemetryResult,
)

# Callable that validates workspace state before running tests.
# Signature: (run_input, repo_root, logs, phase) -> None. Raises WorkspaceError if invalid.
PreTestValidator = Callable[[RunInput, Path, list[str], str], None]


def _noop_validator(run_input: RunInput, repo_root: Path, logs: list[str], phase: str) -> None:
    """Default no-op validator when no dataset-specific validation is needed."""


@dataclass(frozen=True)
class _IterationPrep:
    """Cohesive preparation state for one iteration."""

    identity: RunIdentity
    started_at: str
    started_monotonic: float
    iteration_telemetry: IterationTelemetry
    before_snapshot: object  # opaque snapshot from WorkspaceManager


@dataclass(frozen=True)
class IterationRunner:
    """Coordinates one APR iteration with focused collaborators."""

    agent_runner: AgentExecutionRunner
    workspace: WorkspaceManager
    output_builder: RunOutputBuilder
    stop_policy: StopPolicy = field(default_factory=StopPolicy)
    pre_test_validator: PreTestValidator = _noop_validator

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def execute_iteration(
        self,
        *,
        run_input: RunInput,
        cfg: RunConfig,
        state: RunState,
        iteration: int,
        agent_builder_override: Callable[[], object] | None = None,
    ) -> RunOutput | None:
        """Execute one APR iteration.

        Args:
            agent_builder_override: When provided, use this factory to build the agent
                instead of cfg.facade_agent_builder. Used by PhasedIterationStrategy to
                swap agents between phases without mutating cfg.
        """
        # Phase 1: Prepare
        prep = self._prepare(run_input=run_input, cfg=cfg, state=state, iteration=iteration)

        # Phase 2: Run agent
        agent_result = self._run_agent(
            run_input=run_input,
            cfg=cfg,
            state=state,
            iteration=iteration,
            prep=prep,
            agent_builder_override=agent_builder_override,
        )

        # Phase 3: Observe results (changes, tests, telemetry)
        observation = self._observe(
            run_input=run_input,
            cfg=cfg,
            state=state,
            iteration=iteration,
            prep=prep,
            agent_result=agent_result,
        )

        # Phase 4: Validate and decide
        validation = validate_iteration(
            proposal=observation.proposal,
            changes=observation.changes,
            current_test_execution=observation.test_execution,
            baseline_test_execution=state.baseline_test_execution,
        )
        state.latest_artifacts["validation"] = validation.details
        record_validation_logs(state=state, validation=validation)

        decision = self._decide_outcome(
            run_input=run_input,
            state=state,
            observation=observation,
            validation=validation,
        )

        # Phase 5: Act on decision
        return self._act_on_decision(
            decision=decision,
            identity=prep.identity,
            run_input=run_input,
            cfg=cfg,
            state=state,
            observation=observation,
            validation=validation,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Phase 1: Prepare
    # ──────────────────────────────────────────────────────────────────────

    def _prepare(
        self,
        *,
        run_input: RunInput,
        cfg: RunConfig,
        state: RunState,
        iteration: int,
    ) -> _IterationPrep:
        identity = build_run_identity(
            run_input=run_input,
            agent_config=cfg.agent_config,
            iteration=iteration,
            run_id=cfg.run_id,
        )
        started_at = utc_now_iso()
        started_monotonic = time.perf_counter()

        iteration_telemetry = cfg.observability.telemetry.start_iteration(
            iteration_id=identity.iteration_id,
            iteration_index=iteration,
        )

        new_branch = self.workspace.ensure_temp_branch(
            repo_root=cfg.repo_root,
            run_id=cfg.run_id,
            run_input_metadata=cfg.run_input_metadata,
            iteration=iteration,
            current_branch=state.temp_branch,
            logs=state.accumulated_logs,
        )
        if new_branch is not None:
            state.temp_branch = new_branch

        before_snapshot = self.workspace.snapshot(cfg.repo_root)
        state.validation_feedback = None

        return _IterationPrep(
            identity=identity,
            started_at=started_at,
            started_monotonic=started_monotonic,
            iteration_telemetry=iteration_telemetry,
            before_snapshot=before_snapshot,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Phase 2: Run agent
    # ──────────────────────────────────────────────────────────────────────

    def _run_agent(
        self,
        *,
        run_input: RunInput,
        cfg: RunConfig,
        state: RunState,
        iteration: int,
        prep: _IterationPrep,
        agent_builder_override: Callable[[], object] | None,
    ) -> AgentExecutionResult:
        agent_builder = agent_builder_override or cfg.facade_agent_builder
        agent = agent_builder()
        agent_context = AgentExecutionContext(
            run_agent_id=cfg.run_agent_id,
            run_agent_ids=cfg.run_agent_ids,
            agent_context=cfg.agent_context,
            iteration_telemetry=prep.iteration_telemetry,
            user_input=build_iteration_input(
                prompt=run_input.prompt,
                iteration=iteration,
                max_iterations=cfg.max_iterations,
                previous_message=state.final_message,
                latest_snapshot=state.latest_snapshot,
                baseline_test_execution=state.baseline_test_execution,
                test_command=run_input.test_command,
                validation_feedback=state.validation_feedback,
                repo_root=cfg.repo_root,
            ),
            max_turns=cfg.settings.max_turns,
        )
        prep.iteration_telemetry.record_facade_input(input_text=agent_context.user_input)
        return self.agent_runner.invoke_agent(
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

    # ──────────────────────────────────────────────────────────────────────
    # Phase 3: Observe results
    # ──────────────────────────────────────────────────────────────────────

    def _observe(
        self,
        *,
        run_input: RunInput,
        cfg: RunConfig,
        state: RunState,
        iteration: int,
        prep: _IterationPrep,
        agent_result: AgentExecutionResult,
    ) -> IterationObservation:
        changes = self.workspace.inspect_changes(
            repo_root=cfg.repo_root, before_snapshot=prep.before_snapshot
        )
        self._write_iteration_patch(cfg=cfg, iteration=iteration, diff=changes.diff)
        self.pre_test_validator(run_input, cfg.repo_root, state.accumulated_logs, "iteration")

        test_execution = run_test_command(
            run_input.test_command,
            cwd=cfg.repo_root,
            timeout_seconds=cfg.test_timeout_seconds,
        )

        prep.iteration_telemetry.record_test_execution(
            phase="iteration_validation",
            command=run_input.test_command,
            exit_code=test_execution.exit_code,
            timed_out=test_execution.timed_out,
            signature=test_execution.signature,
            agent_execution_id=agent_result.agent_execution_id,
        )

        observation = IterationObservation(
            iteration=iteration,
            iteration_id=prep.identity.iteration_id,
            started_at=prep.started_at,
            started_monotonic=prep.started_monotonic,
            proposal=agent_result.proposal,
            agent_execution_id=agent_result.agent_execution_id,
            tool_calls_count=agent_result.tool_calls_count,
            changes=changes,
            test_execution=test_execution,
        )
        self._record_observation(
            iteration_telemetry=prep.iteration_telemetry,
            state=state,
            observation=observation,
        )
        return observation

    # ──────────────────────────────────────────────────────────────────────
    # Phase 4: Decide outcome (pure — no side effects)
    # ──────────────────────────────────────────────────────────────────────

    def _decide_outcome(
        self,
        *,
        run_input: RunInput,
        state: RunState,
        observation: IterationObservation,
        validation: IterationValidationResult,
    ) -> IterationDecision:
        proposal = observation.proposal
        test_execution = observation.test_execution
        changed_files = observation.changes.tracked_changed_files

        if not validation.ok:
            if validation.retryable and state.validation_retries < 1:
                return IterationDecision(
                    action="retry",
                    log_suffix=f"validation_result={validation.failure_type}_retryable",
                )
            return IterationDecision(
                action="stop_validation_failure",
                log_suffix=f"validation_result={validation.failure_type}",
            )

        if self.stop_policy.no_progress(
            state=state,
            proposal=proposal,
            test_execution=test_execution,
            changed_files=changed_files,
        ):
            return IterationDecision(action="stop_no_progress")

        if self.stop_policy.success(
            run_input=run_input,
            proposal=proposal,
            test_execution=test_execution,
            changed_files=changed_files,
        ):
            return IterationDecision(action="stop_success")

        if self.stop_policy.agent_reported_stuck(proposal):
            return IterationDecision(
                action="stop_agent_stuck",
                log_suffix="iteration_result=agent_reported_stuck",
            )

        return IterationDecision(action="continue")

    # ──────────────────────────────────────────────────────────────────────
    # Phase 5: Act on decision
    # ──────────────────────────────────────────────────────────────────────

    def _act_on_decision(
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
        proposal = observation.proposal

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
        self._remember_progress(state=state, proposal=proposal, test_signature=observation.test_execution.signature)
        self._append_iteration_logs(cfg=cfg, state=state, observation=observation)
        return None

    # ──────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────

    def _record_observation(
        self,
        *,
        iteration_telemetry: IterationTelemetry,
        state: RunState,
        observation: IterationObservation,
    ) -> None:
        self._record_state(state=state, observation=observation)

        iteration_telemetry.record_file_changes(
            agent_execution_id=observation.agent_execution_id,
            changes=FileChangeTelemetrySet.from_workspace_changes(observation.changes),
        )

        iteration_telemetry.finish_iteration(
            result=IterationTelemetryResult.from_observation(observation),
        )

    def _record_state(self, *, state: RunState, observation: IterationObservation) -> None:
        proposal = observation.proposal
        observed_files = list(observation.changes.all_changed_files)

        state.total_input_tokens += proposal.input_tokens
        state.total_output_tokens += proposal.output_tokens
        state.total_tokens += proposal.total_tokens
        state.final_message = render_final_message(proposal, observed_files=observed_files)
        state.latest_diff = observation.changes.diff
        state.latest_tests = to_test_results(observation.test_execution)
        state.latest_snapshot = build_continuation_snapshot(
            proposal=proposal,
            changes=observation.changes,
            test_execution=observation.test_execution,
        )
        state.latest_observed_files = observed_files
        state.max_changed_files_count = max(state.max_changed_files_count, len(observed_files))

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

