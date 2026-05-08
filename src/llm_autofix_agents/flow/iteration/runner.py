from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from llm_autofix_agents.architectures.config import AgentFactory
from llm_autofix_agents.contracts import RunIdentity, RunInput, RunOutput, build_run_identity
from llm_autofix_agents.flow.agent_execution import AgentExecutionRunner
from llm_autofix_agents.flow.agent_execution.runner import AgentExecutionContext, AgentExecutionResult
from llm_autofix_agents.flow.execution import run_test_command, to_test_results
from llm_autofix_agents.flow.iteration.decision_enactor import IterationDecisionEnactor
from llm_autofix_agents.flow.lifecycle.logs import record_validation_logs
from llm_autofix_agents.flow.models import IterationObservation, render_final_message
from llm_autofix_agents.flow.policies.decision import decide_iteration_outcome
from llm_autofix_agents.flow.policies.iteration import (
    build_continuation_snapshot,
    build_iteration_input,
)
from llm_autofix_agents.flow.policies.stop import StopPolicy
from llm_autofix_agents.flow.policies.validation import validate_iteration
from llm_autofix_agents.flow.runtime.context import RunConfig, RunState
from llm_autofix_agents.flow.workspace.manager import WorkspaceManager
from llm_autofix_agents.observability import utc_now_iso
from llm_autofix_agents.observability.telemetry import IterationTelemetry
from llm_autofix_agents.observability.telemetry_models import (
    FileChangeTelemetrySet,
    IterationTelemetryResult,
)


@runtime_checkable
class PreTestValidator(Protocol):
    """Validates workspace state before running tests. Raises WorkspaceError if invalid."""

    def __call__(self, *, run_input: RunInput, repo_root: Path, logs: list[str], phase: str) -> None: ...


def _noop_validator(*, run_input: RunInput, repo_root: Path, logs: list[str], phase: str) -> None:
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
    outcome_enactor: IterationDecisionEnactor
    agent_factory: AgentFactory
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
    ) -> RunOutput | None:
        """Execute one APR iteration."""
        # Phase 1: Prepare
        prep = self._prepare(run_input=run_input, cfg=cfg, state=state, iteration=iteration)

        # Phase 2: Run agent
        agent_result = self._run_agent(
            run_input=run_input,
            cfg=cfg,
            state=state,
            iteration=iteration,
            prep=prep,
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

        decision = decide_iteration_outcome(
            observation=observation,
            validation=validation,
            state=state,
            run_input=run_input,
            stop_policy=self.stop_policy,
        )

        # Phase 5: Enact decision
        return self.outcome_enactor.enact(
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
    ) -> AgentExecutionResult:
        agent = self.agent_factory()
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
            provider=cfg.provider,
            agent=agent,
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
        self.pre_test_validator(
            run_input=run_input, repo_root=cfg.repo_root, logs=state.accumulated_logs, phase="iteration"
        )

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

