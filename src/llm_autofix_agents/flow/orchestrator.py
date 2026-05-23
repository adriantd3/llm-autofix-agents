from __future__ import annotations

import traceback as _traceback

from llm_autofix_agents.architectures.config import BuiltArchitecture
from llm_autofix_agents.contracts import RunInput, RunOutput, RunStatus, StopReason, build_run_identity
from llm_autofix_agents.flow.agent_execution import AgentExecutionRunner
from llm_autofix_agents.flow.errors import error_category_from_exception
from llm_autofix_agents.flow.execution import resolve_test_timeout_seconds, run_test_command
from llm_autofix_agents.flow.iteration.decision_enactor import IterationDecisionEnactor
from llm_autofix_agents.flow.iteration.runner import IterationRunner
from llm_autofix_agents.flow.lifecycle.finalizer import RunFinalizer
from llm_autofix_agents.flow.lifecycle.output_builder import RunOutputBuilder
from llm_autofix_agents.flow.policies.stop import StopPolicy
from llm_autofix_agents.flow.runtime.context import RunConfig, RunState
from llm_autofix_agents.flow.runtime.initializer import RunInitializer
from llm_autofix_agents.flow.runtime.options import resolve_iteration_timeout_seconds, resolve_max_iterations
from llm_autofix_agents.flow.strategy import IterationStrategy, StandardIterationStrategy
from llm_autofix_agents.flow.workspace.manager import WorkspaceManager
from llm_autofix_agents.flow.workspace.validators import validate_bugsinpy_workspace
from llm_autofix_agents.llm.provider import LLMProvider
from llm_autofix_agents.llm.settings import LLMSettings


class RunOrchestrator:
    """Top-level APR run coordinator.

    Responsibilities:
    - start runtime context,
    - run optional baseline validation,
    - iterate architecture strategy,
    - finalize terminal outputs.

    It intentionally does not build observability DTOs, inspect git details, or map
    validation errors directly.
    """

    def __init__(
        self,
        *,
        architecture: BuiltArchitecture,
        initializer: RunInitializer | None = None,
        iteration_runner: IterationRunner | None = None,
        output_builder: RunOutputBuilder | None = None,
        finalizer: RunFinalizer | None = None,
        workspace: WorkspaceManager | None = None,
        stop_policy: StopPolicy | None = None,
    ) -> None:
        self._initializer = initializer or RunInitializer(architecture=architecture)
        self._workspace = workspace or WorkspaceManager()
        self._output_builder = output_builder or RunOutputBuilder()
        self._finalizer = finalizer or RunFinalizer()
        resolved_stop_policy = stop_policy or StopPolicy()
        _outcome_enactor = IterationDecisionEnactor(
            workspace=self._workspace,
            output_builder=self._output_builder,
        )
        self._iteration_runner = iteration_runner or IterationRunner(
            agent_runner=AgentExecutionRunner(),
            workspace=self._workspace,
            outcome_enactor=_outcome_enactor,
            agent_factory=architecture.facade_agent_builder,
            stop_policy=resolved_stop_policy,
            pre_test_validator=self._pre_test_validator,
        )
        self._strategy: IterationStrategy = self._build_strategy(
            architecture=architecture,
            stop_policy=resolved_stop_policy,
        )

    def run(
        self,
        *,
        run_input: RunInput,
        settings: LLMSettings,
        provider: LLMProvider,
    ) -> RunOutput:
        cfg, state = self._start_run(run_input=run_input, settings=settings, provider=provider)

        try:
            state.baseline_test_execution = self._run_baseline_tests(
                run_input=run_input, cfg=cfg, state=state
            )
            if (
                state.baseline_test_execution is not None
                and state.baseline_test_execution.exit_code == 0
                and not state.baseline_test_execution.timed_out
            ):
                state.accumulated_logs.append(
                    "baseline_already_passes: test suite passed before any agent intervention; "
                    "no fix needed — skipping agent execution"
                )
                return self._finalizer.finalize(
                    output=self._output_builder.build(
                        identity=build_run_identity(
                            run_input=run_input,
                            agent_config=cfg.agent_config,
                            iteration=1,
                            run_id=cfg.run_id,
                        ),
                        status=RunStatus.SUCCESS,
                        stop_reason=StopReason.BASELINE_ALREADY_PASSES,
                        state=state,
                    ),
                    state=state,
                    cfg=cfg,
                )
            return self._run_iterations(run_input=run_input, cfg=cfg, state=state)
        except Exception as exc:
            output = self._output_builder.exception_failure(
                identity=build_run_identity(
                    run_input=run_input,
                    agent_config=cfg.agent_config,
                    iteration=max(state.current_iteration, 1),
                    run_id=cfg.run_id,
                ),
                state=state,
                message=f"{type(exc).__name__}: {exc}",
                category=error_category_from_exception(exc),
                details={
                    "exception_type": type(exc).__name__,
                    "traceback": _traceback.format_exc(),
                },
            )
            self._workspace.restore_temp_branch_for_debug(
                repo_root=cfg.repo_root,
                temp_branch=state.temp_branch,
                logs=state.accumulated_logs,
            )
            return self._finalizer.finalize(output=output, state=state, cfg=cfg)

    def _start_run(
        self,
        *,
        run_input: RunInput,
        settings: LLMSettings,
        provider: LLMProvider,
    ) -> tuple[RunConfig, RunState]:
        return self._initializer.initialize(
            run_input=run_input,
            settings=settings,
            provider=provider,
            max_iterations=resolve_max_iterations(run_input.metadata),
            test_timeout_seconds=resolve_test_timeout_seconds(run_input.metadata),
            iteration_timeout_seconds=resolve_iteration_timeout_seconds(run_input.metadata),
        )

    def _run_baseline_tests(self, *, run_input: RunInput, cfg: RunConfig, state: RunState):
        if run_input.test_command is None:
            return None

        self._validate_bugsinpy_workspace(run_input=run_input, cfg=cfg, state=state, phase="baseline")

        execution = run_test_command(
            run_input.test_command,
            cwd=cfg.repo_root,
            timeout_seconds=cfg.test_timeout_seconds,
        )
        cfg.observability.emitter.record_test_execution(
            None,
            phase="baseline",
            command=run_input.test_command,
            exit_code=execution.exit_code,
            timed_out=execution.timed_out,
            signature=execution.signature,
            iteration=0,
        )
        state.accumulated_logs.extend(
            [
                f"baseline_test_exit_code={execution.exit_code}",
                f"baseline_test_signature={execution.signature}",
            ]
        )
        return execution

    @staticmethod
    def _pre_test_validator(*, run_input: RunInput, repo_root, logs: list[str], phase: str) -> None:
        """Adapter for the PreTestValidator protocol."""
        validate_bugsinpy_workspace(run_input=run_input, repo_root=repo_root, logs=logs, phase=phase)

    def _validate_bugsinpy_workspace(
        self,
        *,
        run_input: RunInput,
        cfg: RunConfig,
        state: RunState,
        phase: str,
    ) -> None:
        validate_bugsinpy_workspace(
            run_input=run_input, repo_root=cfg.repo_root, logs=state.accumulated_logs, phase=phase
        )

    def _run_iterations(self, *, run_input: RunInput, cfg: RunConfig, state: RunState) -> RunOutput:
        return self._strategy.run_iterations(run_input=run_input, cfg=cfg, state=state)

    def _build_strategy(
        self,
        *,
        architecture: BuiltArchitecture,
        stop_policy: StopPolicy,
    ) -> IterationStrategy:
        if architecture.iteration_strategy_factory is not None:
            return architecture.iteration_strategy_factory(
                iteration_runner=self._iteration_runner,
                workspace=self._workspace,
                output_builder=self._output_builder,
                finalizer=self._finalizer,
                stop_policy=stop_policy,
            )
        return StandardIterationStrategy(
            iteration_runner=self._iteration_runner,
            workspace=self._workspace,
            output_builder=self._output_builder,
            finalizer=self._finalizer,
        )


