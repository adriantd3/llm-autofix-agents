from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pydantic import SecretStr

from llm_autofix_agents.llm.provider import OpenAIAgentsSDKProvider, create_provider
from llm_autofix_agents.llm.settings import LLMSettings, ProviderType


class LLMProviderTests(unittest.TestCase):
    @patch("llm_autofix_agents.llm.provider.set_tracing_disabled")
    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_returns_string_output(self, runner_run: AsyncMock, set_tracing_disabled: AsyncMock) -> None:
        runner_run.return_value = SimpleNamespace(final_output="  fix strategy  ")
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())

        result = asyncio.run(
            provider.run_prompt(
                instructions="repair",
                user_input="failing test output",
                max_turns=2,
            )
        )

        self.assertEqual(result, "fix strategy")
        set_tracing_disabled.assert_called_once_with(True)
        self.assertTrue(runner_run.await_count == 1)

    @patch("llm_autofix_agents.llm.provider.MCPServerManager")
    @patch("llm_autofix_agents.llm.provider.Agent")
    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_forwards_mcp_servers_to_agent(
        self,
        runner_run: AsyncMock,
        agent_ctor: AsyncMock,
        mcp_manager_ctor: AsyncMock,
    ) -> None:
        runner_run.return_value = SimpleNamespace(final_output="ok")
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())
        configured_server = object()
        connected_server = object()

        manager = AsyncMock()
        manager.active_servers = [connected_server]
        manager.__aenter__.return_value = manager
        manager.__aexit__.return_value = None
        mcp_manager_ctor.return_value = manager

        asyncio.run(
            provider.run_prompt(
                instructions="repair",
                user_input="failing test output",
                max_turns=2,
                mcp_servers=[configured_server],
            )
        )

        mcp_manager_ctor.assert_called_once_with(
            [configured_server],
            drop_failed_servers=True,
            strict=False,
            connect_in_parallel=True,
        )
        self.assertTrue(agent_ctor.called)
        self.assertEqual(agent_ctor.call_args.kwargs["mcp_servers"], [connected_server])

    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_serializes_non_string_output(self, runner_run: AsyncMock) -> None:
        runner_run.return_value = SimpleNamespace(final_output={"plan": "edit file"})
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())

        result = asyncio.run(
            provider.run_prompt(
                instructions="repair",
                user_input="failing test output",
                max_turns=2,
            )
        )

        self.assertIn('"plan": "edit file"', result)

    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_rejects_empty_output(self, runner_run: AsyncMock) -> None:
        runner_run.return_value = SimpleNamespace(final_output="   ")
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())

        with self.assertRaisesRegex(RuntimeError, "empty output"):
            asyncio.run(
                provider.run_prompt(
                    instructions="repair",
                    user_input="failing test output",
                    max_turns=2,
                )
            )

    @patch("llm_autofix_agents.llm.provider.AsyncOpenAI")
    def test_provider_uses_ollama_fallback_api_key(self, async_openai: AsyncMock) -> None:
        provider = OpenAIAgentsSDKProvider(
            settings=LLMSettings(
                provider=ProviderType.OLLAMA,
                model="llama3.1:8b",
                api_key=None,
                base_url="http://localhost:11434/v1",
                max_turns=3,
                tracing_disabled=True,
            )
        )

        provider._build_model()

        async_openai.assert_called_once_with(api_key="ollama", base_url="http://localhost:11434/v1")

    def test_create_provider_returns_sdk_adapter(self) -> None:
        provider = create_provider(_gemini_settings())
        self.assertIsInstance(provider, OpenAIAgentsSDKProvider)


def _gemini_settings() -> LLMSettings:
    return LLMSettings(
        provider=ProviderType.GEMINI,
        model="gemini-2.5-flash",
        api_key=SecretStr("gemini-key"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        max_turns=3,
        tracing_disabled=True,
    )


if __name__ == "__main__":
    unittest.main()
