from __future__ import annotations

import time
from dataclasses import dataclass, field

from llm_autofix_agents.contracts import RunInput, RunOutput, build_run_identity
from llm_autofix_agents.flow.architecture import ArchitectureRunner
from llm_autofix_agents.flow.execution.tests import run_test_command
from llm_autofix_agents.flow.iteration.context_builder import IterationContextBuilder
from llm_autofix_agents.flow.iteration.decision import IterationOutcomeHandler
from llm_autofix_agents.flow.iteration.recorder import IterationObservation, IterationRecorder
from llm_autofix_agents.flow.lifecycle.logs import record_validation_logs
from llm_autofix_agents.flow.lifecycle.output_builder import RunOutputBuilder
from llm_autofix_agents.flow.policies.stop import StopPolicy
from llm_autofix_agents.flow.policies.validation import validate_iteration
from llm_autofix_agents.flow.runtime.context import RunConfig, RunState
from llm_autofix_agents.flow.workspace.manager import WorkspaceManager
from llm_autofix_agents.observability import utc_now_iso


@dataclass(frozen=True)
class IterationRunner:
    """Coordinates one APR iteration with focused collaborators."""

    architecture: ArchitectureRunner
    workspace: WorkspaceManager
    output_builder: RunOutputBuilder
    stop_policy: StopPolicy = field(default_factory=StopPolicy)
    context_builder: IterationContextBuilder = field(default_factory=IterationContextBuilder)
    recorder: IterationRecorder | None = None
    outcome_handler: IterationOutcomeHandler | None = None

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

        recorder = self.recorder or IterationRecorder()
        outcome_handler = self.outcome_handler or IterationOutcomeHandler(
            workspace=self.workspace,
            output_builder=self.output_builder,
            stop_policy=self.stop_policy,
        )

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
        agent_result = self.architecture.run_iteration(
            self.context_builder.build(
                run_input=run_input,
                cfg=cfg,
                state=state,
                iteration=iteration,
            )
        )

        changes = self.workspace.inspect_changes(cfg=cfg, before_snapshot=before_snapshot)
        test_execution = run_test_command(
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
        recorder.record(
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

        output = outcome_handler.evaluate(
            identity=identity,
            run_input=run_input,
            cfg=cfg,
            state=state,
            observation=observation,
            validation=validation,
        )
        if output is not None:
            return output

        recorder.remember_progress(
            state=state,
            proposal=agent_result.proposal,
            test_signature=test_execution.signature,
        )
        recorder.append_iteration_logs(
            cfg=cfg,
            state=state,
            iteration=iteration,
            changes=changes,
            test_execution=test_execution,
            confidence=agent_result.proposal.confidence,
        )
        return None
