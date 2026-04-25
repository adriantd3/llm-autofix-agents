from __future__ import annotations

from dataclasses import dataclass

from llm_autofix_agents.contracts import RunInput, build_run_identity
from llm_autofix_agents.flow.architecture import AgentIterationContext
from llm_autofix_agents.flow.policies.iteration import build_iteration_input
from llm_autofix_agents.flow.runtime.context import RunConfig, RunState


@dataclass(frozen=True)
class IterationContextBuilder:
    """Builds architecture context for one iteration."""

    def build(
        self,
        *,
        run_input: RunInput,
        cfg: RunConfig,
        state: RunState,
        iteration: int,
    ) -> AgentIterationContext:
        identity = build_run_identity(
            run_input=run_input,
            agent_config=cfg.agent_config,
            iteration=iteration,
            run_id=cfg.run_id,
        )
        iteration_telemetry = cfg.telemetry.start_iteration(
            iteration_id=identity.iteration_id,
            iteration_index=iteration,
        )
        return AgentIterationContext(
            run_id=cfg.run_id,
            iteration_id=identity.iteration_id,
            iteration_index=iteration,
            run_agent_id=cfg.run_agent_id,
            run_input=run_input,
            settings=cfg.settings,
            provider=cfg.provider,
            agent_context=cfg.agent_context,
            agent_tools=cfg.agent_tools,
            iteration_telemetry=iteration_telemetry,
            user_input=build_iteration_input(
                prompt=run_input.prompt,
                iteration=iteration,
                max_iterations=cfg.max_iterations,
                previous_message=state.final_message,
            ),
            max_turns=cfg.settings.max_turns,
        )
