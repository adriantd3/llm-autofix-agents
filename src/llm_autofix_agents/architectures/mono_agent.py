from __future__ import annotations

from llm_autofix_agents.agents.instructions import MONO_AGENT_APR_INSTRUCTIONS
from llm_autofix_agents.architectures.config import BuiltArchitecture
from llm_autofix_agents.llm.agent_factory import build_agent
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.tools.profiles import build_apr_tools


def build_mono_agent_architecture(
    *,
    settings: LLMSettings,
    tool_profile: str | None = None,
) -> BuiltArchitecture:
    resolved_profile = tool_profile or "full"
    tools = build_apr_tools(resolved_profile)

    def build_facade_agent():
        return build_agent(
            settings=settings,
            name="baseline",
            instructions=MONO_AGENT_APR_INSTRUCTIONS,
            tools=tools,
        )

    return BuiltArchitecture(
        architecture_name="mono_agent",
        facade_agent_builder=build_facade_agent,
        agent_name="baseline",
        agent_role="fixer",
        instructions=MONO_AGENT_APR_INSTRUCTIONS,
        tool_profile=resolved_profile,
        tool_count=len(tools),
    )
