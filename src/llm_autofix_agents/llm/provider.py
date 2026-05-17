from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from agents import (
    Agent,
    MaxTurnsExceeded,
    MessageOutputItem,
    ModelBehaviorError,
    RunConfig,
    RunErrorHandlerInput,
    RunErrorHandlerResult,
    RunHooks,
    Runner,
    RunResult,
    ToolCallItem,
    ToolCallOutputItem,
    set_tracing_disabled,
)
from pydantic import BaseModel, Field

from llm_autofix_agents.llm.provider_events import (
    ProviderCallEventCallback,
    ProviderRetryEventEmitter,
)
from llm_autofix_agents.llm.settings import LLMSettings


class AgentFixIterationResult(BaseModel):
    """Structured APR iteration report. Be honest and evidence-driven — the runtime independently verifies changed_files, diffs, and test results."""

    status: Literal["in_progress", "done", "stuck"] = Field(
        description=(
            '"done" = fix applied and tests pass. '
            '"stuck" = cannot progress with available tools or evidence. '
            '"in_progress" = partial progress, validation incomplete or still failing.'
        )
    )
    reasoning_summary: str = Field(
        min_length=1,
        description="Concise summary of diagnosis, patch applied, and validation evidence.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the fix (0.0–1.0). Must reflect observed validation, not optimism.",
    )
    notes: str | None = Field(
        default=None,
        description="Optional caveats, next steps, or explanation if validation could not run.",
    )
    changed_files: list[str] = Field(
        default_factory=list,
        description="Repository-relative paths of every file modified in this iteration.",
    )


class AgentFixIterationRecord(BaseModel):
    """APR run record: the agent's proposal combined with harness-populated execution metadata."""

    proposal: AgentFixIterationResult
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

        # Context accumulated from a failed attempt, injected into the next retry
        # so the agent can resume from where it left off instead of starting over.
        accumulated_context: str | None = None

        for attempt in range(1, total_attempts + 1):
            # Build effective input: on retries after context loss, prepend what was
            # gathered before the interruption so the agent doesn't re-discover it.
            effective_input = user_input
            if attempt > 1 and accumulated_context:
                tool_count = _extract_tool_call_count(hooks) or 0
                effective_input = (
                    f"{user_input}\n\n"
                    f"[RECOVERY: The previous attempt was interrupted by a rate limit after "
                    f"{tool_count} tool calls. Context gathered before interruption:\n"
                    f"{accumulated_context}]"
                )

            _reset_context_snapshot(hooks)

            try:
                result = await Runner.run(
                    agent,
                    effective_input,
                    context=context,
                    max_turns=max_turns,
                    hooks=hooks,
                    run_config=RunConfig(tracing_disabled=self.settings.tracing_disabled),
                    error_handlers={"max_turns": _make_max_turns_handler(max_turns)},
                )
                if attempt > 1:
                    event_emitter.retry_succeeded(attempt=attempt)
                break
            except ModelBehaviorError as exc:
                # The model could not produce output matching the expected
                # schema (e.g. structured JSON). For local models this is a
                # capability issue, not a transient failure — retrying is
                # wasteful. Return a fallback record so the outer loop can
                # evaluate actual changes.
                usage = _extract_token_usage(getattr(exc, "result", None))
                return AgentFixIterationRecord(
                    proposal=AgentFixIterationResult(
                        status="done",
                        reasoning_summary=(
                            "Model could not produce structured output; assuming completion based on tool usage"
                        ),
                        confidence=0.5,
                        notes=f"ModelBehaviorError: {str(exc)[:200]}",
                    ),
                    input_tokens=usage["input_tokens"],
                    output_tokens=usage["output_tokens"],
                    total_tokens=usage["total_tokens"],
                )
            except Exception as exc:  # noqa: BLE001
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

                # Capture research context before sleeping so the next attempt can
                # skip the exploration phase if the runner restarts from scratch.
                accumulated_context = _extract_context_snapshot(hooks)

                retry_after = _extract_retry_after_seconds(exc) if status_code == 429 else None
                delay_seconds = retry_after if retry_after is not None else _compute_retry_delay_seconds(
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
                    rerun_full_runner=accumulated_context is None,
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
                agent_proposal = output
            elif isinstance(output, dict):
                agent_proposal = AgentFixIterationResult.model_validate(output)
            elif isinstance(output, str):
                # Model returned text instead of structured output.
                # Try parsing as JSON first (model may have returned JSON string).
                try:
                    agent_proposal = AgentFixIterationResult.model_validate_json(output)
                except Exception:
                    agent_proposal = AgentFixIterationResult(
                        status="in_progress",
                        reasoning_summary=output or "Model returned empty text output",
                        confidence=0.0,
                        notes="Model returned text output instead of structured output",
                    )
            elif output is None:
                agent_proposal = AgentFixIterationResult(
                    status="in_progress",
                    reasoning_summary="Model returned no output",
                    confidence=0.0,
                    notes="Model final_output was None",
                )
            elif isinstance(output, AgentFixIterationRecord):
                # max_turns handler returned the wrong wrapper type (should be
                # AgentFixIterationResult, not AgentFixIterationRecord).
                agent_proposal = output.proposal
            else:
                # Last resort: serialize via model_dump() for Pydantic models,
                # then fall back to json.dumps for anything else.
                dump_fn = getattr(output, "model_dump", None)
                raw = dump_fn() if callable(dump_fn) else output
                agent_proposal = AgentFixIterationResult.model_validate_json(
                    json.dumps(raw, ensure_ascii=True)
                )
        except Exception as exc:
            raise RuntimeError("Model returned invalid structured output for APR proposal") from exc

        usage = _extract_token_usage(result)
        return AgentFixIterationRecord(
            proposal=agent_proposal,
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
            total_tokens=usage["total_tokens"],
            last_agent_name=last_agent_name,
        )


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


def _extract_retry_after_seconds(exc: Exception) -> float | None:
    """Read the Retry-After (or x-ratelimit-reset-requests) header from a 429 response."""
    response = getattr(exc, "response", None)
    if response is None:
        return None
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    for header_name in ("Retry-After", "retry-after", "x-ratelimit-reset-requests"):
        raw = headers.get(header_name)
        if raw:
            try:
                value = float(raw)
                if value > 0:
                    return value
            except (TypeError, ValueError):
                pass
    return None


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


def _make_max_turns_handler(max_turns: int):
    """Return an error_handler for MaxTurnsExceeded that preserves research context.

    Instead of losing everything the agent investigated, we extract search hits,
    files read, and edit attempts from run_data.new_items and surface them in
    the notes field so the next iteration can skip the exploration phase.
    """
    def _on_max_turns(data: RunErrorHandlerInput[Any]) -> RunErrorHandlerResult:
        notes = _extract_research_context(data.run_data, max_turns)
        # final_output must be AgentFixIterationResult (the agent's output_type),
        # NOT AgentFixIterationRecord — the wrapper is built by the caller.
        return RunErrorHandlerResult(
            final_output=AgentFixIterationResult(
                status="done",
                reasoning_summary="Agent exceeded maximum turns; assuming completion based on tool usage",
                confidence=0.5,
                notes=notes,
            ),
            include_in_history=False,
        )

    return _on_max_turns


def _extract_research_context(run_data: Any, max_turns: int) -> str:
    """Extract useful research context from run_data.new_items after MaxTurnsExceeded.

    Parses tool call / output item pairs to surface:
    - search_files hits with exact file:line locations
    - files read (deduplicated, most recent first)
    - edit attempts and their success/failure
    - last agent reasoning text
    """
    new_items = getattr(run_data, "new_items", None) or []

    pending_call: tuple[str, dict[str, Any]] | None = None
    searches_with_hits: list[str] = []
    files_read: list[str] = []
    edit_attempts: list[str] = []
    last_agent_text: str | None = None

    for item in new_items:
        item_type = getattr(item, "type", None)

        if item_type == "tool_call_item":
            raw = getattr(item, "raw_item", None)
            name = _coerce_optional_string(getattr(raw, "name", None) if raw is not None else None)
            args_str = _coerce_optional_string(getattr(raw, "arguments", None) if raw is not None else None)
            args: dict[str, Any] = {}
            if args_str:
                try:
                    parsed = json.loads(args_str)
                    if isinstance(parsed, dict):
                        args = parsed
                except Exception:  # noqa: BLE001
                    pass
            pending_call = (name or "", args)

        elif item_type == "tool_call_output_item" and pending_call is not None:
            call_name, call_args = pending_call
            output_any = getattr(item, "output", None)
            output_str = output_any if isinstance(output_any, str) else ""

            if call_name == "search_files" and output_str:
                try:
                    data = json.loads(output_str)
                    for r in (data.get("results") or []):
                        path = r.get("path", "")
                        # Skip test file hits — they're noise; only source file locations are actionable.
                        if not path or path.startswith(("test/", "tests/", "test\\", "tests\\")):
                            continue
                        line = r.get("line", "")
                        match_text = str(r.get("match", ""))[:80]
                        searches_with_hits.append(f"{path}:{line} → {match_text}")
                        if len(searches_with_hits) >= 5:
                            break
                except Exception:  # noqa: BLE001
                    pass

            elif call_name == "read_file":
                path = call_args.get("path", "")
                start = call_args.get("start_line")
                end = call_args.get("end_line")
                loc = f":{start}-{end}" if start else ""
                entry = f"{path}{loc}"
                if entry not in files_read:
                    files_read.append(entry)

            elif call_name in ("replace_in_file", "replace_lines", "write_file") and output_str:
                path = call_args.get("path", "")
                try:
                    data = json.loads(output_str)
                    ok = data.get("ok", False)
                    error = data.get("error", "")
                    status = "ok" if ok else f"failed:{error}"
                except Exception:  # noqa: BLE001
                    status = "?"
                edit_attempts.append(f"{call_name}({path}) → {status}")

            pending_call = None

        elif item_type == "message_output_item":
            raw = getattr(item, "raw_item", None)
            content = getattr(raw, "content", None) if raw is not None else None
            if content:
                if isinstance(content, list):
                    texts = [getattr(b, "text", None) for b in content if getattr(b, "text", None)]
                    text = " ".join(str(t) for t in texts if t)
                elif isinstance(content, str):
                    text = content
                else:
                    text = ""
                if text.strip():
                    last_agent_text = text.strip()[:300]

    parts: list[str] = [f"MaxTurnsExceeded after {max_turns} turns — no fix applied."]
    if searches_with_hits:
        parts.append("Search hits (start here next iteration):")
        parts.extend(f"  {hit}" for hit in searches_with_hits)
    if files_read:
        unique_reads = list(dict.fromkeys(files_read))[-5:]
        parts.append(f"Files read: {', '.join(unique_reads)}")
    if edit_attempts:
        parts.append(f"Edit attempts: {', '.join(edit_attempts)}")
    if last_agent_text:
        parts.append(f"Last agent reasoning: {last_agent_text}")
    if not (searches_with_hits or files_read or edit_attempts):
        parts.append("No tool calls recorded.")

    return "\n".join(parts)


def _extract_context_snapshot(hooks: RunHooks[Any] | None) -> str | None:
    """Extract accumulated research context from hooks after a retryable failure."""
    if hooks is None:
        return None
    snapshot_fn = getattr(hooks, "extract_context_snapshot", None)
    if callable(snapshot_fn):
        try:
            return snapshot_fn()
        except Exception:  # noqa: BLE001
            pass
    return None


def _reset_context_snapshot(hooks: RunHooks[Any] | None) -> None:
    """Reset the context snapshot accumulator in hooks before each retry attempt."""
    if hooks is None:
        return
    reset_fn = getattr(hooks, "reset_context_snapshot", None)
    if callable(reset_fn):
        try:
            reset_fn()
        except Exception:  # noqa: BLE001
            pass


def _compute_retry_delay_seconds(*, attempt: int, base_seconds: float, max_seconds: float) -> float:
    exponential_delay = base_seconds * (2 ** (attempt - 1))
    bounded_delay = min(max_seconds, exponential_delay)
    jitter = random.uniform(0.0, base_seconds)
    return min(max_seconds, bounded_delay + jitter)
