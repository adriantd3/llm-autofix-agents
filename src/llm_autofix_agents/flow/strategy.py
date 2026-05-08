"""Iteration strategies for APR architectures.

Each architecture can provide its own iteration strategy that controls:
- How many iterations to run and in what order
- Which agent to use per iteration
- When to stop (phase-aware stop logic)

The default StandardIterationStrategy implements the classic loop
used by mono_agent, multi_agent_handoff, and multi_agent_orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from llm_autofix_agents.contracts import RunInput, RunOutput, RunStatus, StopReason, build_run_identity
from llm_autofix_agents.flow.policies.stop import StopPolicy

if TYPE_CHECKING:
    from llm_autofix_agents.flow.iteration.runner import IterationRunner
    from llm_autofix_agents.flow.lifecycle.finalizer import RunFinalizer
    from llm_autofix_agents.flow.lifecycle.output_builder import RunOutputBuilder
    from llm_autofix_agents.flow.runtime.context import RunConfig, RunState
    from llm_autofix_agents.flow.workspace.manager import WorkspaceManager


class IterationStrategy(Protocol):
    """Protocol for architecture-specific iteration control."""

    def run_iterations(
        self,
        *,
        run_input: RunInput,
        cfg: RunConfig,
        state: RunState,
    ) -> RunOutput: ...


@dataclass(frozen=True)
class StandardIterationStrategy:
    """Standard iteration loop: iterate until success, stuck, or max iterations.

    Used by mono_agent, multi_agent_handoff, and multi_agent_orchestrator.
    """

    iteration_runner: IterationRunner
    workspace: WorkspaceManager
    output_builder: RunOutputBuilder
    finalizer: RunFinalizer

    def run_iterations(
        self,
        *,
        run_input: RunInput,
        cfg: RunConfig,
        state: RunState,
    ) -> RunOutput:
        for iteration in range(1, cfg.max_iterations + 1):
            output = self.iteration_runner.execute_iteration(
                run_input=run_input,
                cfg=cfg,
                state=state,
                iteration=iteration,
            )
            if output is not None:
                return self.finalizer.finalize(output=output, state=state, cfg=cfg)

        self.workspace.restore_temp_branch_for_debug(
            repo_root=cfg.repo_root,
            temp_branch=state.temp_branch,
            logs=state.accumulated_logs,
        )
        return self.finalizer.finalize(
            output=self.output_builder.build(
                identity=build_run_identity(
                    run_input=run_input,
                    agent_config=cfg.agent_config,
                    iteration=cfg.max_iterations,
                    run_id=cfg.run_id,
                ),
                status=RunStatus.PARTIAL,
                stop_reason=StopReason.MAX_ITERATIONS,
                state=state,
            ),
            state=state,
            cfg=cfg,
        )


class PlannerStopPolicy(StopPolicy):
    """During planner phase, never declare success or stuck.

    The planner produces a plan but doesn't fix anything. Only validation
    failures (workspace corruption) should stop the planner phase.
    """

    def success(self, **kwargs) -> bool:  # type: ignore[override]
        return False

    def no_progress(self, **kwargs) -> bool:  # type: ignore[override]
        return False

    def agent_reported_stuck(self, proposal) -> bool:
        return False


@dataclass(frozen=True)
class PhasedIterationStrategy:
    """Phased iteration: phase 1 (planner), phase 2+ (executor).

    The planner investigates and produces a repair plan. Its output
    flows to the executor via RunState (final_message, latest_snapshot).
    The executor applies the fix and is subject to normal stop logic.

    Each runner owns its own agent_factory, so no agent_builder_override
    is needed — the planner_runner builds planner agents, the executor_runner
    builds executor agents.
    """

    planner_runner: IterationRunner
    executor_runner: IterationRunner
    workspace: WorkspaceManager
    output_builder: RunOutputBuilder
    finalizer: RunFinalizer

    def run_iterations(
        self,
        *,
        run_input: RunInput,
        cfg: RunConfig,
        state: RunState,
    ) -> RunOutput:
        # Phase 1: Planner — investigate and produce repair plan.
        # PlannerStopPolicy ensures this never terminates early.
        planner_output = self.planner_runner.execute_iteration(
            run_input=run_input,
            cfg=cfg,
            state=state,
            iteration=1,
        )
        if planner_output is not None:
            # Only validation failures can stop the planner phase.
            return self.finalizer.finalize(output=planner_output, state=state, cfg=cfg)

        # Phase 2+: Executor — apply the fix using the planner's output.
        for iteration in range(2, cfg.max_iterations + 1):
            output = self.executor_runner.execute_iteration(
                run_input=run_input,
                cfg=cfg,
                state=state,
                iteration=iteration,
            )
            if output is not None:
                return self.finalizer.finalize(output=output, state=state, cfg=cfg)

        self.workspace.restore_temp_branch_for_debug(
            repo_root=cfg.repo_root,
            temp_branch=state.temp_branch,
            logs=state.accumulated_logs,
        )
        return self.finalizer.finalize(
            output=self.output_builder.build(
                identity=build_run_identity(
                    run_input=run_input,
                    agent_config=cfg.agent_config,
                    iteration=cfg.max_iterations,
                    run_id=cfg.run_id,
                ),
                status=RunStatus.PARTIAL,
                stop_reason=StopReason.MAX_ITERATIONS,
                state=state,
            ),
            state=state,
            cfg=cfg,
        )


class IterationStrategyFactory(Protocol):
    """Factory that builds an architecture-specific iteration strategy."""

    def __call__(
        self,
        *,
        iteration_runner: IterationRunner,
        workspace: WorkspaceManager,
        output_builder: RunOutputBuilder,
        finalizer: RunFinalizer,
        stop_policy: StopPolicy,
    ) -> IterationStrategy: ...
