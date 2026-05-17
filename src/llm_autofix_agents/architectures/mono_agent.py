from __future__ import annotations

from llm_autofix_agents.agents.instructions import MONO_AGENT_APR_INSTRUCTIONS
from llm_autofix_agents.agents.instructions._dynamic import make_action_biased_instructions
from llm_autofix_agents.architectures.config import BuiltArchitecture
from llm_autofix_agents.llm.agent_factory import build_agent
from llm_autofix_agents.llm.agent_models import resolve_agent_model
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.tools.profiles import build_apr_tools


def build_mono_agent_architecture(
    *,
    settings: LLMSettings,
    agent_models: dict[str, str] | None = None,
    tool_profile: str | None = None,
) -> BuiltArchitecture:
    resolved_profile = tool_profile or "full"
    tools = build_apr_tools(resolved_profile)
    resolved_model = resolve_agent_model(
        agent_models,
        role="main",
        default_model=settings.model,
    )

    def build_facade_agent():
        return build_agent(
            settings=settings,
            name="baseline",
            instructions=make_action_biased_instructions(MONO_AGENT_APR_INSTRUCTIONS),
            tools=tools,
            model_override=resolved_model,
            output_schema=None,
        )

    return BuiltArchitecture(
        architecture_name="mono_agent",
        facade_agent_builder=build_facade_agent,
        agent_name="baseline",
        agent_role="fixer",
        agent_model=resolved_model,
        instructions=MONO_AGENT_APR_INSTRUCTIONS,
        tool_profile=resolved_profile,
        tool_count=len(tools),
    )
