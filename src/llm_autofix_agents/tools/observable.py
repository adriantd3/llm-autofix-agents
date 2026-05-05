from __future__ import annotations

import json
from typing import Any

from agents import FunctionTool

from llm_autofix_agents.observability.tool_context import current_tool_args
from llm_autofix_agents.observability.tool_summaries import summarize_tool_args


def _wrap_invoker(tool: FunctionTool) -> None:
    """Monkey-patch the FunctionTool's internal invoker to capture args."""
    invoker = tool.on_invoke_tool

    # _FailureHandlingFunctionToolInvoker has _invoke_tool_impl
    if hasattr(invoker, "_invoke_tool_impl"):
        original_impl = invoker._invoke_tool_impl

        async def wrapped_impl(ctx: Any, input_json: str) -> Any:
            try:
                parsed = json.loads(input_json)
                if isinstance(parsed, dict):
                    args_summary = summarize_tool_args(tool.name, parsed)
                    current_tool_args.set(args_summary)
            except (json.JSONDecodeError, TypeError):
                pass
            return await original_impl(ctx, input_json)

        invoker._invoke_tool_impl = wrapped_impl
    else:
        # Fallback: the invoker is a plain callable
        async def wrapped_invoker(ctx: Any, input_json: str) -> Any:
            try:
                parsed = json.loads(input_json)
                if isinstance(parsed, dict):
                    args_summary = summarize_tool_args(tool.name, parsed)
                    current_tool_args.set(args_summary)
            except (json.JSONDecodeError, TypeError):
                pass
            return await invoker(ctx, input_json)

        tool.on_invoke_tool = wrapped_invoker  # type: ignore[method-assign]


def make_observable(tool: FunctionTool) -> FunctionTool:
    """Wrap an SDK FunctionTool to capture args_summary before invocation.

    This patches the internal invoker so that args are captured even after
    the SDK copies/rebinds the tool during agent setup.
    """
    _wrap_invoker(tool)
    return tool
