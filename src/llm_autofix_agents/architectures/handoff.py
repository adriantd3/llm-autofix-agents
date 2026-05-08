from __future__ import annotations

from contextvars import ContextVar

from agents import Agent, handoff
from agents.handoffs import HandoffInputData
from agents.items import ItemHelpers, TResponseInputItem
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


_pending_handoff_prompt: ContextVar[APRHandoffInput | None] = ContextVar(
    "pending_handoff_prompt",
    default=None,
)


async def _on_handoff_with_note(ctx: object, note: APRHandoffInput) -> None:
    pending_handoff_note.set(note.model_dump())
    _pending_handoff_prompt.set(note)


def _format_handoff_note(note: APRHandoffInput) -> str:
    lines = ["Handoff summary (from previous agent):", f"- summary: {note.summary}"]
    if note.suspected_files:
        files = ", ".join(note.suspected_files)
        lines.append(f"- suspected_files: {files}")
    if note.evidence:
        evidence = "; ".join(note.evidence)
        lines.append(f"- evidence: {evidence}")
    if note.next_focus:
        lines.append(f"- next_focus: {note.next_focus}")
    if note.confidence is not None:
        lines.append(f"- confidence: {note.confidence:.2f}")
    return "\n".join(lines)


def _normalize_input_history(
    input_history: str | tuple[TResponseInputItem, ...],
) -> list[TResponseInputItem]:
    if isinstance(input_history, str):
        return ItemHelpers.input_to_new_input_list(input_history)
    return list(input_history)


def _handoff_input_filter(handoff_input_data: HandoffInputData) -> HandoffInputData:
    note = _pending_handoff_prompt.get()
    _pending_handoff_prompt.set(None)
    if note is None:
        return handoff_input_data

    # Preserve the original user prompt (first item) and append the handoff note
    history_items: list[TResponseInputItem] = []
    raw_history = _normalize_input_history(handoff_input_data.input_history)
    if raw_history:
        first = raw_history[0]
        if isinstance(first, dict) and first.get("role") == "user":
            history_items.append(first)

    history_items.append({"role": "user", "content": _format_handoff_note(note)})
    return handoff_input_data.clone(
        input_history=tuple(history_items),
        pre_handoff_items=(),
        new_items=(),
    )


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
                    input_filter=_handoff_input_filter,
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
                    input_filter=_handoff_input_filter,
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
                    input_filter=_handoff_input_filter,
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
