from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast

from agents import (
    Agent,
    AgentOutputSchema,
    OpenAIChatCompletionsModel,
    RunConfig,
    Runner,
    RunResult,
    Tool,
    set_tracing_disabled,
)
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from llm_autofix_agents.llm.settings import LLMSettings


class AgentFixIterationResult(BaseModel):
    status: Literal["in_progress", "done", "stuck"]
    reasoning_summary: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str | None = None


class AgentFixIterationRecord(AgentFixIterationResult):
    changed_files: list[str] = Field(default_factory=list)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    tool_calls: list[dict[str, str | None]] = Field(default_factory=list)


class LLMProvider(Protocol):
    async def run_prompt(
        self,
        *,
        instructions: str,
        user_input: str,
        max_turns: int,
        tools: Sequence[object] | None = None,
        context: Any | None = None,
    ) -> AgentFixIterationRecord:
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
        context: Any | None = None,
    ) -> AgentFixIterationRecord:
        set_tracing_disabled(self.settings.tracing_disabled)

        resolved_tools = cast(list[Tool], list(tools) if tools is not None else [])
        result = await Runner.run(
            self._build_agent(
                instructions=instructions,
                tools=resolved_tools,
            ),
            user_input,
            context=context,
            max_turns=max_turns,
            run_config=RunConfig(tracing_disabled=self.settings.tracing_disabled),
        )

        output = result.final_output

        try:
            if isinstance(output, AgentFixIterationResult):
                # convertir a record para poder añadir métricas
                proposal = AgentFixIterationRecord(**output.model_dump())
            elif isinstance(output, dict):
                proposal = AgentFixIterationRecord.model_validate(output)
            else:
                proposal = AgentFixIterationRecord.model_validate_json(json.dumps(output, ensure_ascii=True))
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
    ) -> Agent[Any]:
        return Agent(
            name="AutofixBaselineAgent",
            instructions=instructions,
            model=self._build_model(),
            tools=tools,
            output_type=AgentOutputSchema(AgentFixIterationRecord, strict_json_schema=False),
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


def _extract_token_usage(result: RunResult) -> dict[str, int]:
    usage = getattr(getattr(result, "context_wrapper", None), "usage", None)
    if not usage:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)

    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _extract_tool_calls(result: RunResult) -> list[dict[str, str | None]]:
    tool_entries: list[dict[str, str | None]] = []
    items = getattr(result, "new_items", None) or []

    for item in items:
        raw_item: dict[str, Any] | None = None
        item_type: str | None = None

        if isinstance(item, dict):
            item_type = _coerce_optional_string(item.get("type"))
            raw_item = item
        else:
            item_type = _coerce_optional_string(getattr(item, "type", None))
            raw_item = _to_plain_dict(getattr(item, "raw_item", None))

        if item_type != "tool_call_item" and not _looks_like_tool_call_payload(raw_item):
            continue
        if raw_item is None:
            continue

        name = _coerce_optional_string(raw_item.get("name")) or _coerce_optional_string(raw_item.get("tool_name"))
        if not name:
            continue

        tool_entries.append(
            {
                "name": name,
                "status": _coerce_optional_string(raw_item.get("status")),
            }
        )

    return tool_entries


def _looks_like_tool_call_payload(payload: dict[str, Any] | None) -> bool:
    if payload is None:
        return False

    payload_type = _coerce_optional_string(payload.get("type"))
    if payload_type in {
        "function_call",
        "computer_call",
        "file_search_call",
        "web_search_call",
        "tool_search_call",
        "mcp_call",
        "shell_call",
        "apply_patch_call",
        "hosted_tool_call",
        "local_shell_call",
        "tool_call",
    }:
        return True

    return bool(payload.get("name") or payload.get("tool_name"))


def _coerce_optional_string(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None

    normalized = str(value).strip()
    return normalized or None


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
