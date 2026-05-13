"""Tool observability metadata types.

Each APR tool declares its own ToolDescriptor next to its implementation and
registers it via :func:`llm_autofix_agents.tools.registry.register`.

Dependency arrow: observability → tools.metadata  (never the reverse).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping


class ToolResultKind(str, Enum):
    """Shape of the raw string a tool returns."""

    JSON_ENVELOPE = "json_envelope"  # default: {"ok": bool, ...}
    AGENT_PROSE = "agent_prose"      # Agent.as_tool() returns free-form text
    RAW_TEXT = "raw_text"            # plain string (not JSON)


class ToolStatus(str, Enum):
    """Closed set of tool-call result statuses.

    UNKNOWN must never appear in production; its presence triggers a test failure.
    """

    OK = "ok"
    TOOL_ERROR = "tool_error"
    SDK_ERROR = "sdk_error"
    EMPTY = "empty"
    UNKNOWN = "unknown"


# Prefix strings that indicate the OpenAI Agents SDK itself failed,
# not the tool. Sourced from SDK source: agents/run_internal/tool_execution.py.
_SDK_ERROR_PREFIXES: tuple[str, ...] = (
    "An error occurred while running the tool",
    "Error invoking tool",
    "Error: model",
    "Tool ",
)


def classify_json_envelope(result: str) -> tuple[ToolStatus, bool | None]:
    """Default status classifier for tools that return {"ok": bool, ...}."""
    if any(result.startswith(p) for p in _SDK_ERROR_PREFIXES):
        return ToolStatus.SDK_ERROR, None
    try:
        payload = json.loads(result)
    except json.JSONDecodeError:
        return ToolStatus.UNKNOWN, None
    if not isinstance(payload, dict):
        return ToolStatus.UNKNOWN, None
    ok = payload.get("ok")
    if ok is True:
        return ToolStatus.OK, True
    if ok is False:
        return ToolStatus.TOOL_ERROR, False
    return ToolStatus.UNKNOWN, None


def classify_agent_prose(result: str) -> tuple[ToolStatus, bool | None]:
    """Status classifier for Agent.as_tool() wrappers (return prose text)."""
    stripped = result.strip()
    if not stripped:
        return ToolStatus.EMPTY, None
    if any(stripped.startswith(p) for p in _SDK_ERROR_PREFIXES):
        return ToolStatus.SDK_ERROR, None
    return ToolStatus.OK, True


def classify_raw_text(result: str) -> tuple[ToolStatus, bool | None]:
    """Status classifier for tools that return plain non-JSON strings."""
    stripped = result.strip()
    if not stripped:
        return ToolStatus.EMPTY, None
    if any(stripped.startswith(p) for p in _SDK_ERROR_PREFIXES):
        return ToolStatus.SDK_ERROR, None
    return ToolStatus.OK, True


# ---------------------------------------------------------------------------
# Shared summarizer utilities (may be used by any tool module).
# ---------------------------------------------------------------------------


def content_hash(data: str) -> str:
    """Return a 16-char hex SHA-256 digest of *data*."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def truncate_str(value: str, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    return value[:max_len] + "... [truncated]"


def make_json_result_summarizer(
    inner: Callable[[dict[str, Any], Any], dict[str, Any]],
) -> Callable[[str], dict[str, Any]]:
    """Adapt a (payload, ok) summarizer into a (raw_result_str) → dict function.

    Handles JSON-parse errors gracefully so each per-tool summarizer can focus
    on the happy path without boilerplate.
    """

    def _summarize(raw: str) -> dict[str, Any]:
        try:
            payload: dict[str, Any] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"ok": None, "error_summary": truncate_str(raw, 200)}
        if not isinstance(payload, dict):
            return {"ok": None, "raw_type": type(payload).__name__}
        return inner(payload, payload.get("ok"))

    return _summarize


@dataclass(frozen=True)
class ToolDescriptor:
    """Observability metadata for a single APR tool.

    Phases that consume each field:
    - SH1: summarize_args, summarize_result
    - SH3: classify_status, result_kind
    - SH3+: format_live
    """

    name: str
    result_kind: ToolResultKind
    summarize_args: Callable[[Mapping[str, Any]], dict[str, Any]]
    summarize_result: Callable[[str], dict[str, Any]]
    classify_status: Callable[[str], tuple[ToolStatus, bool | None]] = field(
        default=classify_json_envelope
    )
    # format_live: optional per-tool live.md renderer.  Receives a ToolCallRecord
    # (typed as Any to avoid an observability → tools dependency cycle).
    format_live: Callable[[Any], list[str]] | None = field(default=None)
