from __future__ import annotations

from contextvars import ContextVar

pending_handoff_note: ContextVar[dict | None] = ContextVar("pending_handoff_note", default=None)
