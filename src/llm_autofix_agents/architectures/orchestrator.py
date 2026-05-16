"""Multi-agent orchestrator architecture (v2).

SDK LIMITATION (documented, not fixed):
    The explorer sub-agent is invoked via Agent.as_tool(), which means the SDK
    does NOT propagate the orchestrator's RunHooks into the nested Runner.run()
    call. As a result, the explorer's internal read_file/search_files tool calls
    are invisible to APRRunHooks and never appear in tool_calls.  Only the outer
    explore_code call is recorded — it carries the explorer's prose answer in
    result_summary_json, which surfaces in live.md.

    Reference: OpenAI Agents SDK agent.py:826-839, run_internal/tool_execution.py.
"""
from __future__ import annotations

from typing import Any, Mapping

from agents import Agent

from llm_autofix_agents.agents.instructions import (
    ORCHESTRATOR_V2_EXPLORER_INSTRUCTIONS,
    ORCHESTRATOR_V2_MAIN_INSTRUCTIONS,
)
from llm_autofix_agents.architectures.config import BuiltArchitecture, SubAgent
from llm_autofix_agents.llm.agent_factory import build_agent
from llm_autofix_agents.llm.agent_models import resolve_agent_model
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.tools.metadata import ToolDescriptor, ToolResultKind, classify_agent_prose, truncate_str
from llm_autofix_agents.tools.profiles import build_apr_tools
from llm_autofix_agents.tools.registry import register as _register_tool


def build_multi_agent_orchestrator_architecture(
    *,
    settings: LLMSettings,
    agent_models: dict[str, str] | None = None,
) -> BuiltArchitecture:
    orchestrator_model = resolve_agent_model(
        agent_models,
        role="orchestrator",
        default_model=settings.model,
    )

    def build_facade_agent() -> Agent[object]:
        explorer_agent = build_agent(
            settings=settings,
            name="explorer",
            instructions=ORCHESTRATOR_V2_EXPLORER_INSTRUCTIONS,
            tools=build_apr_tools("explorer"),
            model_override=orchestrator_model,
            output_schema=None,
        )

        orchestrator_tools = build_apr_tools("orchestrator_main") + [
            explorer_agent.as_tool(
                tool_name="explore_code",
                tool_description=(
                    "Delegate to a read-only explorer agent to trace cross-module interactions "
                    "that cannot be resolved with a single search_files + read_file call — "
                    "for example, how an interface propagates across multiple files or where a "
                    "call chain originates. Do NOT use when you already know the file name or "
                    "symbol name: use read_file + search_files directly instead."
                ),
                max_turns=5,
            ),
        ]

        orchestrator_agent = build_agent(
            settings=settings,
            name="orchestrator",
            instructions=ORCHESTRATOR_V2_MAIN_INSTRUCTIONS,
            tools=orchestrator_tools,
            model_override=orchestrator_model,
            output_schema=None,
        )
        return orchestrator_agent

    return BuiltArchitecture(
        architecture_name="multi_agent_orchestrator",
        facade_agent_builder=build_facade_agent,
        agent_name="orchestrator",
        agent_role="orchestrator",
        agent_model=orchestrator_model,
        instructions=ORCHESTRATOR_V2_MAIN_INSTRUCTIONS,
        tool_profile="orchestrator_main",
        tool_count=len(build_apr_tools("orchestrator_main")) + 1,  # +1 for explore_code tool
        sub_agents=(
            SubAgent(
                agent_name="explorer",
                agent_role="explorer",
                model=orchestrator_model,
                instructions=ORCHESTRATOR_V2_EXPLORER_INSTRUCTIONS,
                tool_profile="explorer",
                # Explorer is invoked via Agent.as_tool() — not in the SDK run loop.
                # See module docstring for the SDK limitation details.
                participates_in_run_loop=False,
            ),
        ),
    )


def _explore_code_args(args: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in args.items() if v is not None}


def _explore_code_result(raw: str) -> dict[str, Any]:
    stripped = raw.strip()
    return {"answer": truncate_str(stripped, 1000) if stripped else ""}


_register_tool(
    ToolDescriptor(
        name="explore_code",
        result_kind=ToolResultKind.AGENT_PROSE,
        summarize_args=_explore_code_args,
        summarize_result=_explore_code_result,
        classify_status=classify_agent_prose,
    )
)
