from __future__ import annotations

import asyncio
from collections.abc import Coroutine

from llm_autofix_agents.contracts import (
    ErrorCategory,
    RunError,
    RunInput,
    RunOutput,
    RunStatus,
    StopReason,
    build_run_identity,
)
from llm_autofix_agents.llm.provider import LLMProvider, create_provider
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.toolset import build_mcp_servers

_BASELINE_INSTRUCTIONS = (
    "You are an APR baseline agent operating autonomously. "
    "Decide the flow using available MCP tools, avoid hardcoded assumptions, "
    "and provide concise technical guidance grounded in tool outputs."
)


def run_agent_baseline(
    run_input: RunInput,
    *,
    settings: LLMSettings | None = None,
    provider: LLMProvider | None = None,
) -> RunOutput:
    resolved_settings = settings if settings is not None else LLMSettings.from_env()
    resolved_provider = provider if provider is not None else create_provider(resolved_settings)

    identity = build_run_identity(
        run_input=run_input,
        agent_config=resolved_settings.fingerprint_payload(),
        iteration=1,
    )

    mcp_server_count = 0
    try:
        mcp_servers = build_mcp_servers(
            target_repo=run_input.target_repo,
        )
        mcp_server_count = len(mcp_servers)
        final_message = _run_sync(
            resolved_provider.run_prompt(
                instructions=_BASELINE_INSTRUCTIONS,
                user_input=run_input.prompt,
                max_turns=resolved_settings.max_turns,
                mcp_servers=mcp_servers,
            )
        )
    except Exception as exc:
        return RunOutput(
            identity=identity,
            status=RunStatus.FAILED,
            stop_reason=StopReason.INFRA_FAILURE,
            logs=_build_run_logs(
                provider=resolved_settings.provider.value,
                model=resolved_settings.model,
                result="error",
                mcp_server_count=mcp_server_count,
            ),
            errors=[
                RunError(
                    category=ErrorCategory.MODEL,
                    message=str(exc),
                    retryable=False,
                    details={"provider": resolved_settings.provider.value},
                )
            ],
            final_message=None,
        )

    return RunOutput(
        identity=identity,
        status=RunStatus.SUCCESS,
        stop_reason=StopReason.COMPLETED,
        logs=_build_run_logs(
            provider=resolved_settings.provider.value,
            model=resolved_settings.model,
            result="ok",
            mcp_server_count=mcp_server_count,
        ),
        final_message=final_message,
    )


def _run_sync(awaitable: Coroutine[object, object, str]) -> str:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    raise RuntimeError("run_agent_baseline cannot be called from an active event loop")


def _build_run_logs(*, provider: str, model: str, result: str, mcp_server_count: int) -> list[str]:
    return [
        "stage=agent",
        "toolset=mcp-stdio",
        f"mcp_servers={mcp_server_count}",
        f"provider={provider}",
        f"model={model}",
        f"result={result}",
    ]
