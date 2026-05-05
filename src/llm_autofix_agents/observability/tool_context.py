from __future__ import annotations

from contextvars import ContextVar

current_tool_args: ContextVar[dict | None] = ContextVar("current_tool_args", default=None)

pending_handoff_note: ContextVar[dict | None] = ContextVar("pending_handoff_note", default=None)
