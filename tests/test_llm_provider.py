from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pydantic import SecretStr

from llm_autofix_agents.llm.provider import (
    AgentFixProposal,
    OpenAIAgentsSDKProvider,
    create_provider,
)
from llm_autofix_agents.llm.settings import LLMSettings, ProviderType


class LLMProviderTests(unittest.TestCase):
    @patch("llm_autofix_agents.llm.provider.set_tracing_disabled")
    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_returns_structured_output(self, runner_run: AsyncMock, set_tracing_disabled: AsyncMock) -> None:
        runner_run.return_value = SimpleNamespace(
            final_output=AgentFixProposal(
                patch_unified_diff="--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-print('bad')\n+print('good')",
                rationale="Fix wrong literal",
                confidence=0.72,
                changed_files=["a.py"],
            )
        )
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())

        result = asyncio.run(
            provider.run_prompt(
                instructions="repair",
                user_input="failing test output",
                max_turns=2,
            )
        )

        self.assertIsInstance(result, AgentFixProposal)
        self.assertEqual(result.rationale, "Fix wrong literal")
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
        runner_run.return_value = SimpleNamespace(
            final_output=AgentFixProposal(
                patch_unified_diff="--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-print('bad')\n+print('good')",
                rationale="Fix wrong literal",
                confidence=0.72,
                changed_files=["a.py"],
            )
        )
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
    def test_provider_parses_dict_output(self, runner_run: AsyncMock) -> None:
        runner_run.return_value = SimpleNamespace(
            final_output={
                "patch_unified_diff": "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-print('bad')\n+print('good')",
                "rationale": "Fix wrong literal",
                "confidence": 0.72,
                "changed_files": ["a.py"],
            }
        )
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())

        result = asyncio.run(
            provider.run_prompt(
                instructions="repair",
                user_input="failing test output",
                max_turns=2,
            )
        )

        self.assertEqual(result.changed_files, ["a.py"])

    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_enriches_usage_and_tool_calls(self, runner_run: AsyncMock) -> None:
        runner_run.return_value = SimpleNamespace(
            final_output={
                "rationale": "Fix wrong literal",
                "confidence": 0.72,
                "changed_files": ["a.py"],
            },
            usage={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
            new_items=[
                {
                    "type": "tool_call",
                    "name": "shell",
                    "arguments": {"command": "uv run pytest"},
                    "call_id": "call-1",
                    "status": "completed",
                }
            ],
        )
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())

        result = asyncio.run(
            provider.run_prompt(
                instructions="repair",
                user_input="failing test output",
                max_turns=2,
            )
        )

        self.assertEqual(result.input_tokens, 11)
        self.assertEqual(result.output_tokens, 7)
        self.assertEqual(result.total_tokens, 18)
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0]["name"], "shell")

    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_rejects_invalid_schema(self, runner_run: AsyncMock) -> None:
        runner_run.return_value = SimpleNamespace(final_output={"confidence": 0.3})
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())

        with self.assertRaisesRegex(RuntimeError, "invalid structured output"):
            asyncio.run(
                provider.run_prompt(
                    instructions="repair",
                    user_input="failing test output",
                    max_turns=2,
                )
            )

    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_accepts_execution_report_without_patch(self, runner_run: AsyncMock) -> None:
        runner_run.return_value = SimpleNamespace(
            final_output={
                "rationale": "Applied edits via MCP tools and validated with tests",
                "confidence": 0.81,
                "changed_files": ["src/a.py"],
            }
        )
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())

        result = asyncio.run(
            provider.run_prompt(
                instructions="repair",
                user_input="failing test output",
                max_turns=2,
            )
        )

        self.assertIsNone(result.patch_unified_diff)
        self.assertEqual(result.changed_files, ["src/a.py"])

    @patch("llm_autofix_agents.llm.provider.Agent")
    def test_provider_sets_structured_output_type(self, agent_ctor: AsyncMock) -> None:
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())

        provider._build_agent(instructions="repair", tools=[], mcp_servers=None)

        self.assertTrue(agent_ctor.called)
        self.assertIs(agent_ctor.call_args.kwargs["output_type"], AgentFixProposal)

    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_rejects_unparseable_output(self, runner_run: AsyncMock) -> None:
        runner_run.return_value = SimpleNamespace(final_output=object())
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())

        with self.assertRaisesRegex(RuntimeError, "invalid structured output"):
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
