from __future__ import annotations

from llm_autofix_agents.architectures.config import BuiltArchitecture
from llm_autofix_agents.contracts import RunInput, RunOutput, RunStatus, StopReason, build_run_identity
from llm_autofix_agents.flow.agent_execution import AgentExecutionRunner
from llm_autofix_agents.flow.errors import error_category_from_exception
from llm_autofix_agents.flow.execution.tests import resolve_test_timeout_seconds, run_test_command
from llm_autofix_agents.flow.iteration_runner import IterationRunner
from llm_autofix_agents.flow.lifecycle.finalizer import RunFinalizer
from llm_autofix_agents.flow.lifecycle.output_builder import RunOutputBuilder
from llm_autofix_agents.flow.policies.stop import StopPolicy
from llm_autofix_agents.flow.runtime.context import RunConfig, RunState
from llm_autofix_agents.flow.runtime.initializer import RunInitializer
from llm_autofix_agents.flow.runtime.options import resolve_max_iterations
from llm_autofix_agents.flow.workspace.manager import WorkspaceManager
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
        self._architecture = architecture
        self._initializer = initializer or RunInitializer(architecture=architecture)
        self._workspace = workspace or WorkspaceManager()
        self._output_builder = output_builder or RunOutputBuilder()
        self._finalizer = finalizer or RunFinalizer()
        self._iteration_runner = iteration_runner or IterationRunner(
            agent_runner=AgentExecutionRunner(),
            workspace=self._workspace,
            output_builder=self._output_builder,
            stop_policy=stop_policy or StopPolicy(),
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
            cfg.baseline_test_execution = self._run_baseline_tests(run_input=run_input, cfg=cfg, state=state)
            return self._run_iterations(run_input=run_input, cfg=cfg, state=state)
        except Exception as exc:
            output = self._output_builder.exception_failure(
                identity=build_run_identity(
                    run_input=run_input,
                    agent_config=cfg.agent_config,
                    iteration=1,
                    run_id=cfg.run_id,
                ),
                state=state,
                cfg=cfg,
                message=str(exc),
                category=error_category_from_exception(exc),
            )
            self._workspace.restore_temp_branch_for_debug(cfg=cfg, logs=state.accumulated_logs)
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
        )

    def _run_baseline_tests(self, *, run_input: RunInput, cfg: RunConfig, state: RunState):
        if run_input.test_command is None:
            return None

        execution = run_test_command(
            run_input.test_command,
            cwd=cfg.repo_root,
            timeout_seconds=cfg.test_timeout_seconds,
        )
        cfg.telemetry.record_test_execution(
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

    def _run_iterations(self, *, run_input: RunInput, cfg: RunConfig, state: RunState) -> RunOutput:
        for iteration in range(1, cfg.max_iterations + 1):
            output = self._iteration_runner.run(
                run_input=run_input,
                cfg=cfg,
                state=state,
                iteration=iteration,
            )
            if output is not None:
                return self._finalizer.finalize(output=output, state=state, cfg=cfg)

        self._workspace.restore_temp_branch_for_debug(cfg=cfg, logs=state.accumulated_logs)
        return self._finalizer.finalize(
            output=self._output_builder.build(
                identity=build_run_identity(
                    run_input=run_input,
                    agent_config=cfg.agent_config,
                    iteration=cfg.max_iterations,
                    run_id=cfg.run_id,
                ),
                status=RunStatus.PARTIAL,
                stop_reason=StopReason.MAX_ITERATIONS,
                state=state,
                cfg=cfg,
            ),
            state=state,
            cfg=cfg,
        )
