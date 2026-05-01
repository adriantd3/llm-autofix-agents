from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from agents import Agent, AgentOutputSchema, OpenAIChatCompletionsModel, Tool
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions
from openai import AsyncOpenAI

from llm_autofix_agents.llm.provider import AgentFixIterationRecord
from llm_autofix_agents.llm.settings import LLMSettings

_DEFAULT_OUTPUT_SCHEMA = object()


def build_agent(
    *,
    settings: LLMSettings,
    name: str,
    instructions: str,
    tools: Sequence[object],
    model_override: str | None = None,
    output_schema: AgentOutputSchema | None | object = _DEFAULT_OUTPUT_SCHEMA,
    handoffs: Sequence[object] | None = None,
    handoff_description: str | None = None,
) -> Agent[Any]:
    resolved_tools = cast(list[Tool], list(tools))
    resolved_model = _build_model(settings, model_override=model_override)
    model_types: tuple[type, ...] = (str,)
    if isinstance(OpenAIChatCompletionsModel, type):
        model_types = (OpenAIChatCompletionsModel, str)
    if resolved_model is not None and not isinstance(resolved_model, model_types):
        # Fall back to model name when the model is mocked in tests.
        resolved_model = _resolve_model_name(settings, model_override)

    # Prepend SDK-recommended handoff instructions when the agent participates
    # in a handoff chain. This teaches the model to call transfer_to_<name>
    # tools rather than writing about handoffs in its text output.
    resolved_instructions = prompt_with_handoff_instructions(instructions) if handoffs else instructions

    agent_kwargs: dict[str, Any] = {
        "name": name,
        "instructions": resolved_instructions,
        "model": resolved_model,
        "tools": resolved_tools,
    }
    if output_schema is _DEFAULT_OUTPUT_SCHEMA:
        agent_kwargs["output_type"] = AgentOutputSchema(AgentFixIterationRecord, strict_json_schema=False)
    elif output_schema is not None:
        agent_kwargs["output_type"] = output_schema
    if handoffs:
        agent_kwargs["handoffs"] = list(handoffs)
    if handoff_description:
        agent_kwargs["handoff_description"] = handoff_description
    return Agent(**agent_kwargs)


def _build_model(settings: LLMSettings, *, model_override: str | None) -> OpenAIChatCompletionsModel:
    client = AsyncOpenAI(
        api_key=_resolve_api_key(settings),
        base_url=settings.base_url,
    )
    resolved_model = _resolve_model_name(settings, model_override)
    return OpenAIChatCompletionsModel(model=resolved_model, openai_client=client)


def _resolve_model_name(settings: LLMSettings, model_override: str | None) -> str:
    if model_override is None:
        return settings.model
    normalized = model_override.strip()
    if not normalized:
        raise ValueError("model_override cannot be empty")
    return normalized


def _resolve_api_key(settings: LLMSettings) -> str:
    if settings.api_key is None:
        return "ollama"
    resolved = settings.api_key.get_secret_value().strip()
    if not resolved:
        return "ollama"
    return resolved
