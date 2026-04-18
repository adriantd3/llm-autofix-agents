from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

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
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)

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
                proposal = AgentFixProposal.model_validate(output)
            else:
                proposal = AgentFixProposal.model_validate_json(json.dumps(output, ensure_ascii=True))
        except Exception as exc:
            raise RuntimeError("Model returned invalid structured output for APR proposal") from exc

        usage = _extract_token_usage(result)
        proposal.input_tokens = usage["input_tokens"]
        proposal.output_tokens = usage["output_tokens"]
        proposal.total_tokens = usage["total_tokens"]
        proposal.tool_calls = _extract_tool_calls(result)
        return proposal

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


def _extract_token_usage(result: Any) -> dict[str, int]:
    usage_payload = _to_plain_dict(getattr(result, "usage", None))
    if usage_payload is None:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    input_tokens = _as_non_negative_int(usage_payload.get("input_tokens"))
    output_tokens = _as_non_negative_int(usage_payload.get("output_tokens"))
    total_tokens = _as_non_negative_int(usage_payload.get("total_tokens"))
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _extract_tool_calls(result: Any) -> list[dict[str, Any]]:
    raw_items = getattr(result, "new_items", None)
    if not isinstance(raw_items, Sequence):
        return []

    tool_calls: list[dict[str, Any]] = []
    for item in raw_items:
        payload = _to_plain_dict(item)
        if payload is None:
            continue

        kind = str(payload.get("type", ""))
        has_tool_shape = "tool" in kind or "function_call" in kind
        if not has_tool_shape:
            continue

        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            continue

        arguments = payload.get("arguments")
        if arguments is not None and not isinstance(arguments, str):
            arguments = json.dumps(arguments, ensure_ascii=True)

        call_id = payload.get("call_id")
        if call_id is not None and not isinstance(call_id, str):
            call_id = str(call_id)

        status = payload.get("status")
        if status is not None and not isinstance(status, str):
            status = str(status)

        tool_calls.append(
            {
                "name": name,
                "kind": kind,
                "arguments": arguments,
                "call_id": call_id,
                "status": status,
            }
        )
    return tool_calls


def _to_plain_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return dumped

    vars_payload = getattr(value, "__dict__", None)
    if isinstance(vars_payload, dict):
        return vars_payload
    return None


def _as_non_negative_int(value: Any) -> int:
    if not isinstance(value, int):
        return 0
    if value < 0:
        return 0
    return value
