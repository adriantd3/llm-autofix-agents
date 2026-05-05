from __future__ import annotations

from agents import Agent

from llm_autofix_agents.agents.instructions import (
    ORCHESTRATOR_LOCALIZER_INSTRUCTIONS,
    ORCHESTRATOR_MANAGER_INSTRUCTIONS,
    ORCHESTRATOR_PATCHER_INSTRUCTIONS,
    ORCHESTRATOR_VALIDATOR_INSTRUCTIONS,
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
    localizer_tools = build_apr_tools("localizer")
    patcher_tools = build_apr_tools("patcher")
    validator_tools = build_apr_tools("validator")
    tool_names = {
        tool.__name__ for tool in (localizer_tools + patcher_tools + validator_tools) if hasattr(tool, "__name__")
    }

    localizer_model = resolve_agent_model(
        agent_models,
        role="localizer",
        default_model=settings.model,
    )
    patcher_model = resolve_agent_model(
        agent_models,
        role="patcher",
        default_model=settings.model,
    )
    validator_model = resolve_agent_model(
        agent_models,
        role="validator",
        default_model=settings.model,
    )
    manager_model = resolve_agent_model(
        agent_models,
        role="manager",
        default_model=settings.model,
    )

    def build_facade_agent() -> Agent[object]:
        localizer_agent = build_agent(
            settings=settings,
            name="localizer",
            instructions=ORCHESTRATOR_LOCALIZER_INSTRUCTIONS,
            tools=localizer_tools,
            model_override=localizer_model,
            output_schema=None,
        )

        patcher_agent = build_agent(
            settings=settings,
            name="patcher",
            instructions=ORCHESTRATOR_PATCHER_INSTRUCTIONS,
            tools=patcher_tools,
            model_override=patcher_model,
            output_schema=None,
        )

        validator_agent = build_agent(
            settings=settings,
            name="validator",
            instructions=ORCHESTRATOR_VALIDATOR_INSTRUCTIONS,
            tools=validator_tools,
            model_override=validator_model,
            output_schema=None,
        )

        manager_tools = [
            localizer_agent.as_tool(
                tool_name="localize_bug",
                tool_description="Call the localization specialist to identify the most likely faulty files, symbols, and lines. Provide the bug context and receive a structured localization report.",
            ),
            patcher_agent.as_tool(
                tool_name="apply_fix",
                tool_description="Call the patcher specialist to apply a minimal patch based on localization evidence. Provide the localization context and receive a summary of changes made.",
            ),
            validator_agent.as_tool(
                tool_name="validate_patch",
                tool_description="Call the validation specialist to run tests and verify whether the patch works. Provide context about changes made and receive a validation report.",
            ),
        ]

        manager_agent = build_agent(
            settings=settings,
            name="orchestrator",
            instructions=ORCHESTRATOR_MANAGER_INSTRUCTIONS,
            tools=manager_tools,
            model_override=manager_model,
        )
        return manager_agent

    return BuiltArchitecture(
        architecture_name="multi_agent_orchestrator",
        facade_agent_builder=build_facade_agent,
        agent_name="orchestrator",
        agent_role="manager",
        agent_model=manager_model,
        instructions=ORCHESTRATOR_MANAGER_INSTRUCTIONS,
        tool_profile="manager",
        tool_count=len(tool_names),
        sub_agents=(
            SubAgentDescriptor(
                agent_name="localizer",
                agent_role="localizer",
                model=localizer_model,
                instructions=ORCHESTRATOR_LOCALIZER_INSTRUCTIONS,
                tool_profile="localizer",
            ),
            SubAgentDescriptor(
                agent_name="patcher",
                agent_role="patcher",
                model=patcher_model,
                instructions=ORCHESTRATOR_PATCHER_INSTRUCTIONS,
                tool_profile="patcher",
            ),
            SubAgentDescriptor(
                agent_name="validator",
                agent_role="validator",
                model=validator_model,
                instructions=ORCHESTRATOR_VALIDATOR_INSTRUCTIONS,
                tool_profile="validator",
            ),
        ),
    )
