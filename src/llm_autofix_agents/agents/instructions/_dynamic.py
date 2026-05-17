"""Thin shim — kept for import compatibility.

Use ``PromptBuilder`` directly for new code::

    from llm_autofix_agents.agents.instructions.builder import PromptBuilder
    instructions = PromptBuilder(BASE).with_action_bias()
"""
from __future__ import annotations

from llm_autofix_agents.agents.instructions.builder import PromptBuilder


def make_action_biased_instructions(base: str) -> PromptBuilder:
    """Return a PromptBuilder that appends an urgency block during stuck exploration."""
    return PromptBuilder(base).with_action_bias()
