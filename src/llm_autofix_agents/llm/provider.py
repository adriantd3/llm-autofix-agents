from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from agents import Agent, RunConfig, RunHooks, Runner, RunResult, set_tracing_disabled
from pydantic import BaseModel, Field

from llm_autofix_agents.llm.provider_events import (
    ProviderCallEventCallback,
    ProviderRetryEventEmitter,
)
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
    last_agent_name: str | None = None


class LLMProvider(Protocol):
    async def run_agent(
        self,
        *,
        agent: Agent[Any],
        user_input: str,
        max_turns: int,
        context: Any | None = None,
        hooks: RunHooks[Any] | None = None,
        event_callback: ProviderCallEventCallback | None = None,
    ) -> AgentFixIterationRecord:
        """Run a single prompt turn and return a structured APR proposal."""


class ProviderCallError(RuntimeError):
    """Provider-level execution failure with retry context for diagnostics."""

    def __init__(
        self,
        *,
        attempt: int,
        total_attempts: int,
        retryable: bool,
        status_code: int | None,
        cause: Exception,
    ) -> None:
        self.attempt = attempt
        self.total_attempts = total_attempts
        self.retryable = retryable
        self.status_code = status_code
        self.cause = cause
        message = (
            f"provider call failed after {attempt} attempt(s): "
            f"retryable={retryable} status_code={status_code} error={cause.__class__.__name__}: {cause}"
        )
        super().__init__(message)


@dataclass(frozen=True)
class OpenAIAgentsSDKProvider:
    settings: LLMSettings

    async def run_agent(
        self,
        *,
        agent: Agent[Any],
        user_input: str,
        max_turns: int,
        context: Any | None = None,
        hooks: RunHooks[Any] | None = None,
        event_callback: ProviderCallEventCallback | None = None,
    ) -> AgentFixIterationRecord:
        set_tracing_disabled(self.settings.tracing_disabled)

        result: RunResult | None = None
        total_attempts = self.settings.api_max_retries + 1
        agent_execution_id = _extract_agent_execution_id(hooks)
        event_emitter = ProviderRetryEventEmitter(
            callback=event_callback,
            agent_execution_id=agent_execution_id,
            total_attempts=total_attempts,
            tool_calls_count_getter=lambda: _extract_tool_call_count(hooks),
        )

        for attempt in range(1, total_attempts + 1):
            try:
                result = await Runner.run(
                    agent,
                    user_input,
                    context=context,
                    max_turns=max_turns,
                    hooks=hooks,
                    run_config=RunConfig(tracing_disabled=self.settings.tracing_disabled),
                )
                if attempt > 1:
                    event_emitter.retry_succeeded(attempt=attempt)
                break
            except Exception as exc:  # noqa: BLE001
                # MaxTurnsExceeded means the agent used all available turns.
                # Rather than crashing, return a fallback record so the outer
                # iteration loop can still evaluate any file changes / test
                # results that occurred during the run.
                if exc.__class__.__name__ == "MaxTurnsExceeded":
                    # Use "done" so that the outer stop policy can recognize
                    # success when tests pass, even though the agent ran out of
                    # turns before explicitly reporting completion.
                    proposal = AgentFixIterationRecord(
                        status="done",
                        reasoning_summary="Agent exceeded maximum turns; assuming completion based on tool usage",
                        confidence=0.5,
                        changed_files=[],
                        notes=f"MaxTurnsExceeded after {max_turns} turns",
                    )
                    usage = _extract_token_usage(getattr(exc, "result", None))
                    proposal.input_tokens = usage["input_tokens"]
                    proposal.output_tokens = usage["output_tokens"]
                    proposal.total_tokens = usage["total_tokens"]
                    return proposal

                # ModelBehaviorError means the model could not produce output
                # matching the expected schema (e.g. structured JSON). For local
                # models this is a capability issue, not a transient failure,
                # so retrying the entire handoff pipeline is wasteful. Return a
                # fallback record so the outer loop can evaluate actual changes.
                if exc.__class__.__name__ == "ModelBehaviorError":
                    proposal = AgentFixIterationRecord(
                        status="done",
                        reasoning_summary=(
                            "Model could not produce structured output; assuming completion based on tool usage"
                        ),
                        confidence=0.5,
                        changed_files=[],
                        notes=f"ModelBehaviorError: {str(exc)[:200]}",
                    )
                    usage = _extract_token_usage(getattr(exc, "result", None))
                    proposal.input_tokens = usage["input_tokens"]
                    proposal.output_tokens = usage["output_tokens"]
                    proposal.total_tokens = usage["total_tokens"]
                    return proposal

                retryable = _is_retryable_provider_error(exc)
                status_code = _extract_http_status_code(exc)
                if not retryable:
                    event_emitter.non_retryable_failure(
                        attempt=attempt,
                        status_code=status_code,
                        error=exc,
                    )
                    raise ProviderCallError(
                        attempt=attempt,
                        total_attempts=total_attempts,
                        retryable=False,
                        status_code=status_code,
                        cause=exc,
                    ) from exc

                if attempt >= total_attempts:
                    event_emitter.retries_exhausted(
                        attempt=attempt,
                        status_code=status_code,
                        error=exc,
                    )
                    raise ProviderCallError(
                        attempt=attempt,
                        total_attempts=total_attempts,
                        retryable=True,
                        status_code=status_code,
                        cause=exc,
                    ) from exc

                delay_seconds = _compute_retry_delay_seconds(
                    attempt=attempt,
                    base_seconds=self.settings.api_retry_base_seconds,
                    max_seconds=self.settings.api_retry_max_seconds,
                )
                event_emitter.retryable_failure(
                    attempt=attempt,
                    status_code=status_code,
                    error=exc,
                )
                event_emitter.retry_scheduled(
                    attempt=attempt,
                    status_code=status_code,
                    error=exc,
                    retry_delay_seconds=delay_seconds,
                )
                await asyncio.sleep(delay_seconds)

        if result is None:
            unknown_cause = RuntimeError("provider call failed without a result")
            raise ProviderCallError(
                attempt=total_attempts,
                total_attempts=total_attempts,
                retryable=False,
                status_code=None,
                cause=unknown_cause,
            ) from unknown_cause

        last_agent_name = None
        try:
            last_agent = getattr(result, "last_agent", None)
            if last_agent is not None:
                last_agent_name = getattr(last_agent, "name", None)
        except Exception:
            pass

        output = result.final_output

        try:
            if isinstance(output, AgentFixIterationResult):
                # convertir a record para poder añadir métricas
                proposal = AgentFixIterationRecord(**output.model_dump())
            elif isinstance(output, dict):
                proposal = AgentFixIterationRecord.model_validate(output)
            elif isinstance(output, str):
                # Model returned text instead of structured output.
                # Try parsing as JSON first (model may have returned JSON string).
                try:
                    proposal = AgentFixIterationRecord.model_validate_json(output)
                except Exception:
                    # Fallback: wrap text into a minimal record so the pipeline
                    # can continue rather than crashing.
                    proposal = AgentFixIterationRecord(
                        status="in_progress",
                        reasoning_summary=output or "Model returned empty text output",
                        confidence=0.0,
                        changed_files=[],
                        notes="Model returned text output instead of structured AgentFixIterationRecord",
                    )
            elif output is None:
                proposal = AgentFixIterationRecord(
                    status="in_progress",
                    reasoning_summary="Model returned no output",
                    confidence=0.0,
                    changed_files=[],
                    notes="Model final_output was None",
                )
            else:
                proposal = AgentFixIterationRecord.model_validate_json(json.dumps(output, ensure_ascii=True))
        except Exception as exc:
            raise RuntimeError("Model returned invalid structured output for APR proposal") from exc

        usage = _extract_token_usage(result)
        proposal.input_tokens = usage["input_tokens"]
        proposal.output_tokens = usage["output_tokens"]
        proposal.total_tokens = usage["total_tokens"]
        proposal.last_agent_name = last_agent_name

        return proposal


def create_provider(settings: LLMSettings) -> LLMProvider:
    return OpenAIAgentsSDKProvider(settings=settings)


def _extract_token_usage(result: RunResult) -> dict[str, int]:
    if result is None:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    # 1. SDK canonical: accumulated usage on the context wrapper
    usage = getattr(getattr(result, "context_wrapper", None), "usage", None)
    if _has_tokens(usage):
        return _build_usage_dict(usage)

    # 2. Compatibility: direct .usage (older SDK versions, mocks, custom providers)
    usage = getattr(result, "usage", None)
    if _has_tokens(usage):
        return _build_usage_dict(usage)

    # 3. Fallback: sum individual raw response usages
    raw_responses = getattr(result, "raw_responses", None) or []
    total_input = 0
    total_output = 0
    total = 0
    for resp in raw_responses:
        resp_usage = getattr(resp, "usage", None)
        if _has_tokens(resp_usage):
            total_input += _usage_field(resp_usage, "input_tokens")
            total_output += _usage_field(resp_usage, "output_tokens")
            total += _usage_field(resp_usage, "total_tokens")
    if total_input or total_output:
        if total == 0:
            total = total_input + total_output
        return {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total,
        }

    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def _has_tokens(usage: Any) -> bool:
    if usage is None:
        return False
    return bool(_usage_field(usage, "input_tokens") or _usage_field(usage, "output_tokens"))


def _build_usage_dict(usage: Any) -> dict[str, int]:
    input_tokens = _usage_field(usage, "input_tokens")
    output_tokens = _usage_field(usage, "output_tokens")
    total_tokens = _usage_field(usage, "total_tokens")
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _usage_field(usage: Any, field_name: str) -> int:
    if isinstance(usage, dict):
        raw_value = usage.get(field_name, 0)
    else:
        raw_value = getattr(usage, field_name, 0)

    try:
        return int(raw_value or 0)
    except (TypeError, ValueError):
        return 0


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


def _is_retryable_provider_error(exc: Exception) -> bool:
    status_code = _extract_http_status_code(exc)
    if status_code in {408, 409, 425, 429, 500, 502, 503, 504}:
        return True

    class_name = exc.__class__.__name__
    if class_name in {
        "APIConnectionError",
        "APITimeoutError",
        "RateLimitError",
        "InternalServerError",
        "ServiceUnavailableError",
        "ModelBehaviorError",
    }:
        return True

    message = str(exc).lower()
    transient_markers = (
        "timeout",
        "timed out",
        "connection reset",
        "connection aborted",
        "temporarily unavailable",
        "try again",
    )
    return any(marker in message for marker in transient_markers)


def _extract_http_status_code(exc: Exception) -> int | None:
    raw_status = getattr(exc, "status_code", None)
    if isinstance(raw_status, int):
        return raw_status

    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    if isinstance(response_status, int):
        return response_status

    return None


def _extract_agent_execution_id(hooks: RunHooks[Any] | None) -> str | None:
    if hooks is None:
        return None

    candidate = getattr(hooks, "agent_execution_id", None)
    if isinstance(candidate, str) and candidate.strip():
        return candidate

    fallback = getattr(hooks, "_agent_execution_id", None)
    if isinstance(fallback, str) and fallback.strip():
        return fallback
    return None


def _extract_tool_call_count(hooks: RunHooks[Any] | None) -> int | None:
    if hooks is None:
        return None

    raw_value = getattr(hooks, "tool_call_count", None)
    try:
        if raw_value is None:
            return None
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _compute_retry_delay_seconds(*, attempt: int, base_seconds: float, max_seconds: float) -> float:
    exponential_delay = base_seconds * (2 ** (attempt - 1))
    bounded_delay = min(max_seconds, exponential_delay)
    jitter = random.uniform(0.0, base_seconds)
    return min(max_seconds, bounded_delay + jitter)
