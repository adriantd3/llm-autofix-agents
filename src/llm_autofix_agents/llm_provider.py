from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from agents import (
    Agent,
    OpenAIChatCompletionsModel,
    RunConfig,
    Runner,
    set_tracing_disabled,
)
from openai import AsyncOpenAI

from llm_autofix_agents.config import LLMSettings


class LLMProvider(Protocol):
    async def run_prompt(self, *, instructions: str, user_input: str, max_turns: int) -> str:
        """Run a single prompt turn and return plain text output."""


@dataclass(frozen=True)
class OpenAIAgentsSDKProvider:
    settings: LLMSettings

    async def run_prompt(self, *, instructions: str, user_input: str, max_turns: int) -> str:
        set_tracing_disabled(self.settings.tracing_disabled)

        agent = Agent(
            name="AutofixBaselineAgent",
            instructions=instructions,
            model=self._build_model(),
        )
        result = await Runner.run(
            agent,
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
            api_key=self.settings.api_key.get_secret_value(),
            base_url=self.settings.base_url,
        )
        return OpenAIChatCompletionsModel(model=self.settings.model, openai_client=client)


def create_provider(settings: LLMSettings) -> LLMProvider:
    return OpenAIAgentsSDKProvider(settings=settings)
