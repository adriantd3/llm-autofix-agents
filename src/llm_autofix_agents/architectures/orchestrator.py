from __future__ import annotations

from agents import Agent

from llm_autofix_agents.agents.instructions import (
    ORCHESTRATOR_V2_EXPLORER_INSTRUCTIONS,
    ORCHESTRATOR_V2_MAIN_INSTRUCTIONS,
)
from llm_autofix_agents.architectures.config import BuiltArchitecture, SubAgentDescriptor
from llm_autofix_agents.llm.agent_factory import build_agent
from llm_autofix_agents.llm.agent_models import resolve_agent_model
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.tools.profiles import build_apr_tools


def build_multi_agent_orchestrator_architecture(
    *,
    settings: LLMSettings,
    agent_models: dict[str, str] | None = None,
) -> BuiltArchitecture:
    orchestrator_model = resolve_agent_model(
        agent_models,
        role="orchestrator",
        default_model=settings.model,
    )

    def build_facade_agent() -> Agent[object]:
        explorer_agent = build_agent(
            settings=settings,
            name="explorer",
            instructions=ORCHESTRATOR_V2_EXPLORER_INSTRUCTIONS,
            tools=build_apr_tools("explorer"),
            model_override=orchestrator_model,
            output_schema=None,
        )

        orchestrator_tools = build_apr_tools("orchestrator_main") + [
            explorer_agent.as_tool(
                tool_name="explore_code",
                tool_description=(
                    "Delegate to the read-only explorer agent to understand specific source files. "
                    "Provide the file paths to examine and a focused question. "
                    "Returns a compact, targeted summary. Use this instead of reading large files yourself."
                ),
            ),
        ]

        orchestrator_agent = build_agent(
            settings=settings,
            name="orchestrator",
            instructions=ORCHESTRATOR_V2_MAIN_INSTRUCTIONS,
            tools=orchestrator_tools,
            model_override=orchestrator_model,
            output_schema=None,
        )
        return orchestrator_agent

    return BuiltArchitecture(
        architecture_name="multi_agent_orchestrator",
        facade_agent_builder=build_facade_agent,
        agent_name="orchestrator",
        agent_role="orchestrator",
        agent_model=orchestrator_model,
        instructions=ORCHESTRATOR_V2_MAIN_INSTRUCTIONS,
        tool_profile="orchestrator_main",
        tool_count=len(build_apr_tools("orchestrator_main")),
        sub_agents=(
            SubAgentDescriptor(
                agent_name="explorer",
                agent_role="explorer",
                model=orchestrator_model,
                instructions=ORCHESTRATOR_V2_EXPLORER_INSTRUCTIONS,
                tool_profile="explorer",
            ),
        ),
    )
