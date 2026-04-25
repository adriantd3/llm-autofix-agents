from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from agents import AgentOutputSchema
from pydantic import SecretStr

from llm_autofix_agents.llm.provider import (
    AgentFixIterationRecord,
    OpenAIAgentsSDKProvider,
    create_provider,
)
from llm_autofix_agents.llm.settings import LLMSettings, ProviderType


class LLMProviderTests(unittest.TestCase):
    @patch("llm_autofix_agents.llm.provider.set_tracing_disabled")
    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_returns_structured_output(self, runner_run: AsyncMock, set_tracing_disabled: AsyncMock) -> None:
        runner_run.return_value = SimpleNamespace(
            final_output=AgentFixIterationRecord(
                status="done",
                reasoning_summary="Fix wrong literal",
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

        self.assertIsInstance(result, AgentFixIterationRecord)
        self.assertEqual(result.reasoning_summary, "Fix wrong literal")
        set_tracing_disabled.assert_called_once_with(True)
        self.assertTrue(runner_run.await_count == 1)

    @patch("llm_autofix_agents.llm.provider.Agent")
    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_forwards_tools_and_context_to_agent(
        self,
        runner_run: AsyncMock,
        agent_ctor: AsyncMock,
    ) -> None:
        runner_run.return_value = SimpleNamespace(
            final_output=AgentFixIterationRecord(
                status="done",
                reasoning_summary="Fix wrong literal",
                confidence=0.72,
                changed_files=["a.py"],
            )
        )
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())
        configured_tool = object()
        context = object()

        asyncio.run(
            provider.run_prompt(
                instructions="repair",
                user_input="failing test output",
                max_turns=2,
                tools=[configured_tool],
                context=context,
            )
        )

        self.assertTrue(agent_ctor.called)
        self.assertEqual(agent_ctor.call_args.kwargs["tools"], [configured_tool])
        self.assertNotIn("mcp_servers", agent_ctor.call_args.kwargs)
        self.assertEqual(runner_run.await_args.kwargs["context"], context)

    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_parses_dict_output(self, runner_run: AsyncMock) -> None:
        runner_run.return_value = SimpleNamespace(
            final_output={
                "status": "in_progress",
                "reasoning_summary": "Fix wrong literal",
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
        self.assertEqual(result.status, "in_progress")

    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_enriches_usage_and_tool_calls(self, runner_run: AsyncMock) -> None:
        runner_run.return_value = SimpleNamespace(
            final_output={
                "status": "done",
                "reasoning_summary": "Fix wrong literal",
                "confidence": 0.72,
                "changed_files": ["a.py"],
            },
            usage={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
            new_items=[
                {
                    "type": "tool_call",
                    "name": "shell",
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
        self.assertEqual(result.tool_calls[0], {"name": "shell", "status": "completed"})

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
                "status": "done",
                "reasoning_summary": "Applied edits via local tools and validated with tests",
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

        self.assertEqual(result.status, "done")
        self.assertEqual(result.changed_files, ["src/a.py"])

    @patch("llm_autofix_agents.llm.provider.Agent")
    def test_provider_sets_structured_output_type(self, agent_ctor: AsyncMock) -> None:
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())

        provider._build_agent(instructions="repair", tools=[])

        self.assertTrue(agent_ctor.called)
        output_type = agent_ctor.call_args.kwargs["output_type"]
        self.assertIsInstance(output_type, AgentOutputSchema)
        self.assertIs(output_type.output_type, AgentFixIterationRecord)
        self.assertFalse(output_type.is_strict_json_schema())
        self.assertNotIn("mcp_servers", agent_ctor.call_args.kwargs)

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
                base_url="http://localhost:11500/v1",
                max_turns=3,
                tracing_disabled=True,
            )
        )

        provider._build_model()

        async_openai.assert_called_once_with(api_key="ollama", base_url="http://localhost:11500/v1")

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
