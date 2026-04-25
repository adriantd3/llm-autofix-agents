from __future__ import annotations

from dataclasses import dataclass, field

from llm_autofix_agents.flow.agent_execution import AgentExecutionRunner
from llm_autofix_agents.flow.architecture import AgentIterationContext, AgentIterationResult


@dataclass(frozen=True)
class MonoAgentArchitecture:
    """Baseline architecture: one autonomous fixer agent per iteration."""

    instructions: str
    architecture_name: str = "mono_agent"
    agent_name: str = "baseline"
    agent_role: str = "fixer"
    agent_runner: AgentExecutionRunner = field(default_factory=AgentExecutionRunner)

    def run_iteration(self, context: AgentIterationContext) -> AgentIterationResult:
        execution = self.agent_runner.run_agent(
            context=context,
            execution_index=1,
            provider_call=lambda hooks: context.provider.run_prompt(
                instructions=self.instructions,
                user_input=context.user_input,
                max_turns=context.max_turns,
                tools=context.agent_tools,
                context=context.agent_context,
                hooks=hooks,
            ),
        )

        return AgentIterationResult(
            proposal=execution.proposal,
            agent_execution_id=execution.agent_execution_id,
            started_at=execution.started_at,
            duration_seconds=execution.duration_seconds,
            tool_calls_count=execution.tool_calls_count,
        )
