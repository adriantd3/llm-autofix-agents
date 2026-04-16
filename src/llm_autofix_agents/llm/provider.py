from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from agents import (
    Agent,
    OpenAIChatCompletionsModel,
    RunConfig,
    Runner,
    Tool,
    set_tracing_disabled,
)
from agents.mcp import MCPServer, MCPServerManager
from openai import AsyncOpenAI

from llm_autofix_agents.llm.settings import LLMSettings


class LLMProvider(Protocol):
    async def run_prompt(
        self,
        *,
        instructions: str,
        user_input: str,
        max_turns: int,
        tools: Sequence[object] | None = None,
        mcp_servers: Sequence[MCPServer] | None = None,
    ) -> str:
        """Run a single prompt turn and return plain text output."""


@dataclass(frozen=True)
class OpenAIAgentsSDKProvider:
    settings: LLMSettings

    async def run_prompt(
        self,
        *,
        instructions: str,
        user_input: str,
        max_turns: int,
        tools: Sequence[object] | None = None,
        mcp_servers: Sequence[MCPServer] | None = None,
    ) -> str:
        set_tracing_disabled(self.settings.tracing_disabled)

        resolved_tools = cast(list[Tool], list(tools) if tools is not None else [])
        resolved_mcp_servers = list(mcp_servers) if mcp_servers is not None else []

        if resolved_mcp_servers:
            async with MCPServerManager(
                resolved_mcp_servers,
                drop_failed_servers=True,
                strict=False,
                connect_in_parallel=True,
            ) as manager:
                result = await Runner.run(
                    Agent(
                        name="AutofixBaselineAgent",
                        instructions=instructions,
                        model=self._build_model(),
                        tools=resolved_tools,
                        mcp_servers=manager.active_servers,
                    ),
                    user_input,
                    max_turns=max_turns,
                    run_config=RunConfig(tracing_disabled=self.settings.tracing_disabled),
                )
        else:
            result = await Runner.run(
                Agent(
                    name="AutofixBaselineAgent",
                    instructions=instructions,
                    model=self._build_model(),
                    tools=resolved_tools,
                ),
                user_input,
                max_turns=max_turns,
                run_config=RunConfig(tracing_disabled=self.settings.tracing_disabled),
            )

        output = result.final_output
        if isinstance(output, str):
            text_output = output
        else:
            try:
                text_output = json.dumps(output, ensure_ascii=True)
            except TypeError:
                text_output = str(output)

        normalized = text_output.strip()
        if not normalized:
            raise RuntimeError("Model returned empty output")
        return normalized

    def _build_model(self) -> OpenAIChatCompletionsModel:
        client = AsyncOpenAI(
            api_key=self._resolve_api_key(),
            base_url=self.settings.base_url,
        )
        return OpenAIChatCompletionsModel(model=self.settings.model, openai_client=client)

    def _resolve_api_key(self) -> str:
        if self.settings.api_key is None:
            return "ollama"
        resolved = self.settings.api_key.get_secret_value().strip()
        if not resolved:
            return "ollama"
        return resolved


def create_provider(settings: LLMSettings) -> LLMProvider:
    return OpenAIAgentsSDKProvider(settings=settings)
