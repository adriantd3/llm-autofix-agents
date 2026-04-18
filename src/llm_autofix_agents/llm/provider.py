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
from pydantic import BaseModel, Field, field_validator

from llm_autofix_agents.llm.settings import LLMSettings


class AgentFixProposal(BaseModel):
    patch_unified_diff: str | None = None
    rationale: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    changed_files: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("rationale")
    @classmethod
    def _normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be empty")
        return normalized

    @field_validator("patch_unified_diff")
    @classmethod
    def _normalize_optional_patch(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return normalized

    @field_validator("changed_files")
    @classmethod
    def _normalize_changed_files(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("changed_files cannot contain duplicates")
        return normalized


class LLMProvider(Protocol):
    async def run_prompt(
        self,
        *,
        instructions: str,
        user_input: str,
        max_turns: int,
        tools: Sequence[object] | None = None,
        mcp_servers: Sequence[MCPServer] | None = None,
    ) -> AgentFixProposal:
        """Run a single prompt turn and return a structured APR proposal."""


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
    ) -> AgentFixProposal:
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
                    self._build_agent(
                        instructions=instructions,
                        tools=resolved_tools,
                        mcp_servers=manager.active_servers,
                    ),
                    user_input,
                    max_turns=max_turns,
                    run_config=RunConfig(tracing_disabled=self.settings.tracing_disabled),
                )
        else:
            result = await Runner.run(
                self._build_agent(
                    instructions=instructions,
                    tools=resolved_tools,
                    mcp_servers=None,
                ),
                user_input,
                max_turns=max_turns,
                run_config=RunConfig(tracing_disabled=self.settings.tracing_disabled),
            )

        output = result.final_output
        if isinstance(output, AgentFixProposal):
            return output
        try:
            if isinstance(output, dict):
                return AgentFixProposal.model_validate(output)
            return AgentFixProposal.model_validate_json(json.dumps(output, ensure_ascii=True))
        except Exception as exc:
            raise RuntimeError("Model returned invalid structured output for APR proposal") from exc

    def _build_agent(
        self,
        *,
        instructions: str,
        tools: list[Tool],
        mcp_servers: Sequence[MCPServer] | None,
    ) -> Agent[None]:
        return Agent(
            name="AutofixBaselineAgent",
            instructions=instructions,
            model=self._build_model(),
            tools=tools,
            mcp_servers=list(mcp_servers) if mcp_servers is not None else [],
            output_type=AgentFixProposal,
        )

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
