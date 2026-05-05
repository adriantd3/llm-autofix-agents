from __future__ import annotations

from agents import Agent, handoff
from pydantic import BaseModel

from llm_autofix_agents.agents.instructions import (
    HANDOFF_LOCALIZER_INSTRUCTIONS,
    HANDOFF_PATCHER_INSTRUCTIONS,
    HANDOFF_TRIAGE_INSTRUCTIONS,
    HANDOFF_VALIDATOR_INSTRUCTIONS,
)
from llm_autofix_agents.architectures.config import BuiltArchitecture, SubAgentDescriptor
from llm_autofix_agents.llm.agent_factory import build_agent
from llm_autofix_agents.llm.agent_models import resolve_agent_model
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.observability.tool_context import pending_handoff_note
from llm_autofix_agents.tools.profiles import build_apr_tools


class APRHandoffInput(BaseModel):
    summary: str
    evidence: list[str] = []
    suspected_files: list[str] = []
    next_focus: str | None = None
    confidence: float | None = None


async def _on_handoff_with_note(ctx: object, note: APRHandoffInput) -> None:
    pending_handoff_note.set(note.model_dump())


def build_multi_agent_handoff_architecture(
    *,
    settings: LLMSettings,
    agent_models: dict[str, str] | None = None,
) -> BuiltArchitecture:
    triage_tools = build_apr_tools("triage")
    localizer_tools = build_apr_tools("localizer")
    patcher_tools = build_apr_tools("patcher")
    validator_tools = build_apr_tools("validator")
    tool_names = {
        tool.__name__
        for tool in (triage_tools + localizer_tools + patcher_tools + validator_tools)
        if hasattr(tool, "__name__")
    }

    triage_model = resolve_agent_model(
        agent_models,
        role="triage",
        default_model=settings.model,
    )
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

    def build_facade_agent() -> Agent[object]:
        validator_agent = build_agent(
            settings=settings,
            name="validator",
            instructions=HANDOFF_VALIDATOR_INSTRUCTIONS,
            tools=validator_tools,
            model_override=validator_model,
            handoff_description="APR validator that runs final checks and reports results.",
        )

        patcher_agent = build_agent(
            settings=settings,
            name="patcher",
            instructions=HANDOFF_PATCHER_INSTRUCTIONS,
            tools=patcher_tools,
            model_override=patcher_model,
            output_schema=None,
            handoffs=[
                handoff(
                    validator_agent,
                    input_type=APRHandoffInput,
                    on_handoff=_on_handoff_with_note,
                )
            ],
            handoff_description="APR patcher that applies a minimal fix.",
        )

        localizer_agent = build_agent(
            settings=settings,
            name="localizer",
            instructions=HANDOFF_LOCALIZER_INSTRUCTIONS,
            tools=localizer_tools,
            model_override=localizer_model,
            output_schema=None,
            handoffs=[
                handoff(
                    patcher_agent,
                    input_type=APRHandoffInput,
                    on_handoff=_on_handoff_with_note,
                )
            ],
            handoff_description="APR localizer that narrows the faulty code.",
        )

        triage_agent = build_agent(
            settings=settings,
            name="triage",
            instructions=HANDOFF_TRIAGE_INSTRUCTIONS,
            tools=triage_tools,
            model_override=triage_model,
            output_schema=None,
            handoffs=[
                handoff(
                    localizer_agent,
                    input_type=APRHandoffInput,
                    on_handoff=_on_handoff_with_note,
                )
            ],
            handoff_description="APR triage agent that gathers initial signals.",
        )
        return triage_agent

    return BuiltArchitecture(
        architecture_name="multi_agent_handoff",
        facade_agent_builder=build_facade_agent,
        agent_name="triage",
        agent_role="triage",
        agent_model=triage_model,
        instructions=HANDOFF_TRIAGE_INSTRUCTIONS,
        tool_profile="triage",
        tool_count=len(tool_names),
        sub_agents=(
            SubAgentDescriptor(
                agent_name="localizer",
                agent_role="localizer",
                model=localizer_model,
                instructions=HANDOFF_LOCALIZER_INSTRUCTIONS,
                tool_profile="localizer",
            ),
            SubAgentDescriptor(
                agent_name="patcher",
                agent_role="patcher",
                model=patcher_model,
                instructions=HANDOFF_PATCHER_INSTRUCTIONS,
                tool_profile="patcher",
            ),
            SubAgentDescriptor(
                agent_name="validator",
                agent_role="validator",
                model=validator_model,
                instructions=HANDOFF_VALIDATOR_INSTRUCTIONS,
                tool_profile="validator",
            ),
        ),
    )
