from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from agents import Agent, AgentOutputSchema, OpenAIChatCompletionsModel, Tool
from openai import AsyncOpenAI

from llm_autofix_agents.llm.provider import AgentFixIterationRecord
from llm_autofix_agents.llm.settings import LLMSettings


def build_agent(
    *,
    settings: LLMSettings,
    name: str,
    instructions: str,
    tools: Sequence[object],
) -> Agent[Any]:
    resolved_tools = cast(list[Tool], list(tools))
    return Agent(
        name=name,
        instructions=instructions,
        model=_build_model(settings),
        tools=resolved_tools,
        output_type=AgentOutputSchema(AgentFixIterationRecord, strict_json_schema=False),
    )


def _build_model(settings: LLMSettings) -> OpenAIChatCompletionsModel:
    client = AsyncOpenAI(
        api_key=_resolve_api_key(settings),
        base_url=settings.base_url,
    )
    return OpenAIChatCompletionsModel(model=settings.model, openai_client=client)


def _resolve_api_key(settings: LLMSettings) -> str:
    if settings.api_key is None:
        return "ollama"
    resolved = settings.api_key.get_secret_value().strip()
    if not resolved:
        return "ollama"
    return resolved
