"""Composable, SDK-native prompt builder for agent instructions.

``PromptBuilder`` wraps a base instruction string and stacks modifiers via a
fluent API. Because it implements the SDK's ``(RunContextWrapper, Agent) -> str``
callable signature, it can be passed directly to ``Agent.instructions`` — the
SDK re-invokes it on every LLM turn so dynamic modifiers always see fresh state.

Usage::

    from llm_autofix_agents.agents.instructions.builder import PromptBuilder

    instructions = PromptBuilder(BASE_INSTRUCTIONS).with_action_bias()

For agents that participate in handoffs, ``build_agent()`` calls
``.with_handoff_prefix()`` automatically when ``handoffs=[...]`` is passed —
no manual wiring required at the call site.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agents import Agent
    from agents.run_context import RunContextWrapper

# After this many non-edit tool calls with 0 edits, inject an urgency block.
# 6 is conservative: 3 LLM turns × 2 parallel tools = typical initial exploration.
_EXPLORATION_WARNING_THRESHOLD = 6

_URGENCY_BLOCK = """
⚠ ACTION REQUIRED — {n_calls} tool calls made, 0 edits applied.
You have spent your turns on exploration without acting. Stop reading and apply your best fix now:
- If you have a plausible root cause → call replace_in_file immediately. An imperfect fix you can test and refine is better than analysis you never act on.
- If genuinely stuck after trying → set status="stuck".
- Do NOT call search_files or read_file again before making at least one edit attempt.
"""


def _action_bias(prompt: str, ctx: "RunContextWrapper[Any]") -> str:
    tool_ctx = getattr(ctx, "context", None)
    if tool_ctx is None:
        return prompt
    n_calls = getattr(tool_ctx, "iteration_tool_call_count", 0)
    n_edits = getattr(tool_ctx, "iteration_edit_count", 0)
    if n_calls >= _EXPLORATION_WARNING_THRESHOLD and n_edits == 0:
        return prompt + _URGENCY_BLOCK.format(n_calls=n_calls)
    return prompt


def _handoff_prefix(prompt: str, _ctx: "RunContextWrapper[Any]") -> str:
    from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

    return f"{RECOMMENDED_PROMPT_PREFIX}\n\n{prompt}"


class PromptBuilder:
    """Immutable, composable instruction builder for SDK agents.

    Each ``.with_*()`` method returns a **new** ``PromptBuilder`` leaving the
    original unchanged. Modifiers are applied left-to-right when the builder
    is called by the SDK.
    """

    def __init__(self, base: str, _modifiers: tuple = ()) -> None:
        self._base = base
        self._modifiers = _modifiers

    def with_action_bias(self) -> "PromptBuilder":
        """Append an urgency block when the agent is stuck exploring without editing."""
        return PromptBuilder(self._base, self._modifiers + (_action_bias,))

    def with_handoff_prefix(self) -> "PromptBuilder":
        """Prepend the SDK-recommended handoff instructions prefix."""
        return PromptBuilder(self._base, self._modifiers + (_handoff_prefix,))

    def __call__(self, ctx: "RunContextWrapper[Any]", _agent: "Agent[Any]") -> str:
        result = self._base
        for modifier in self._modifiers:
            result = modifier(result, ctx)
        return result
