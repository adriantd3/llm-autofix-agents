from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from agents import AgentOutputSchema, Usage
from pydantic import SecretStr

from llm_autofix_agents.llm.agent_factory import build_agent
from llm_autofix_agents.llm.provider import (
    AgentFixIterationRecord,
    OpenAIAgentsSDKProvider,
    ProviderCallError,
    create_provider,
)
from llm_autofix_agents.llm.provider_events import ProviderCallEvent
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

        result = asyncio.run(provider.run_agent(agent=_stub_agent(), user_input="failing test output", max_turns=2))

        self.assertIsInstance(result, AgentFixIterationRecord)
        self.assertEqual(result.reasoning_summary, "Fix wrong literal")
        set_tracing_disabled.assert_called_once_with(True)
        self.assertTrue(runner_run.await_count == 1)

    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_forwards_agent_and_context(
        self,
        runner_run: AsyncMock,
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
        agent = _stub_agent()
        context = object()

        asyncio.run(provider.run_agent(agent=agent, user_input="failing test output", max_turns=2, context=context))

        self.assertEqual(runner_run.await_args.args[0], agent)
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

        result = asyncio.run(provider.run_agent(agent=_stub_agent(), user_input="failing test output", max_turns=2))

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
            context_wrapper=SimpleNamespace(
                usage=Usage(input_tokens=11, output_tokens=7, total_tokens=18),
            ),
            new_items=[
                {
                    "type": "tool_call",
                    "name": "shell",
                    "status": "completed",
                }
            ],
        )
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())

        result = asyncio.run(provider.run_agent(agent=_stub_agent(), user_input="failing test output", max_turns=2))

        self.assertEqual(result.input_tokens, 11)
        self.assertEqual(result.output_tokens, 7)
        self.assertEqual(result.total_tokens, 18)

    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_falls_back_to_raw_responses_for_usage(self, runner_run: AsyncMock) -> None:
        runner_run.return_value = SimpleNamespace(
            final_output={
                "status": "done",
                "reasoning_summary": "Fix wrong literal",
                "confidence": 0.72,
                "changed_files": ["a.py"],
            },
            context_wrapper=SimpleNamespace(
                usage=Usage(),  # empty accumulated usage
            ),
            raw_responses=[
                SimpleNamespace(usage=Usage(input_tokens=5, output_tokens=3, total_tokens=8)),
                SimpleNamespace(usage=Usage(input_tokens=6, output_tokens=4, total_tokens=10)),
            ],
            new_items=[],
        )
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())

        result = asyncio.run(provider.run_agent(agent=_stub_agent(), user_input="failing test output", max_turns=2))

        self.assertEqual(result.input_tokens, 11)
        self.assertEqual(result.output_tokens, 7)
        self.assertEqual(result.total_tokens, 18)

    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_reads_legacy_usage_attribute(self, runner_run: AsyncMock) -> None:
        runner_run.return_value = SimpleNamespace(
            final_output={
                "status": "done",
                "reasoning_summary": "Fix wrong literal",
                "confidence": 0.72,
                "changed_files": ["a.py"],
            },
            usage={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
            new_items=[],
        )
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())

        result = asyncio.run(provider.run_agent(agent=_stub_agent(), user_input="failing test output", max_turns=2))

        self.assertEqual(result.input_tokens, 11)
        self.assertEqual(result.output_tokens, 7)
        self.assertEqual(result.total_tokens, 18)

    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_rejects_invalid_schema(self, runner_run: AsyncMock) -> None:
        runner_run.return_value = SimpleNamespace(final_output={"confidence": 0.3})
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())

        with self.assertRaisesRegex(RuntimeError, "invalid structured output"):
            asyncio.run(provider.run_agent(agent=_stub_agent(), user_input="failing test output", max_turns=2))

    @patch("llm_autofix_agents.llm.provider.asyncio.sleep", new_callable=AsyncMock)
    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_retries_transient_provider_error_then_succeeds(
        self,
        runner_run: AsyncMock,
        sleep_mock: AsyncMock,
    ) -> None:
        events: list[ProviderCallEvent] = []
        runner_run.side_effect = [
            _TransientProviderError("internal error", status_code=500),
            SimpleNamespace(
                final_output={
                    "status": "done",
                    "reasoning_summary": "Fixed after transient failure",
                    "confidence": 0.77,
                    "changed_files": ["src/a.py"],
                }
            ),
        ]
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())

        result = asyncio.run(
            provider.run_agent(
                agent=_stub_agent(),
                user_input="failing test output",
                max_turns=2,
                event_callback=events.append,
            )
        )

        self.assertEqual(result.status, "done")
        self.assertEqual(runner_run.await_count, 2)
        self.assertEqual(sleep_mock.await_count, 1)
        self.assertEqual(
            [event.event_type for event in events],
            ["retryable_failure", "retry_scheduled", "retry_succeeded"],
        )
        self.assertEqual(events[0].attempt, 1)
        self.assertEqual(events[0].total_attempts, 6)
        self.assertEqual(events[0].status_code, 500)
        self.assertEqual(events[1].retry_delay_seconds, sleep_mock.await_args.args[0])
        self.assertEqual(events[2].attempt, 2)

    @patch("llm_autofix_agents.llm.provider.asyncio.sleep", new_callable=AsyncMock)
    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_does_not_retry_non_retryable_error(
        self,
        runner_run: AsyncMock,
        sleep_mock: AsyncMock,
    ) -> None:
        events: list[ProviderCallEvent] = []
        runner_run.side_effect = RuntimeError("invalid tool call schema")
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())

        with self.assertRaisesRegex(ProviderCallError, "provider call failed after 1 attempt"):
            asyncio.run(
                provider.run_agent(
                    agent=_stub_agent(),
                    user_input="failing test output",
                    max_turns=2,
                    event_callback=events.append,
                )
            )

        self.assertEqual(runner_run.await_count, 1)
        self.assertEqual(sleep_mock.await_count, 0)
        self.assertEqual([event.event_type for event in events], ["non_retryable_failure"])

    @patch("llm_autofix_agents.llm.provider.asyncio.sleep", new_callable=AsyncMock)
    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_logs_and_raises_when_retries_are_exhausted(
        self,
        runner_run: AsyncMock,
        sleep_mock: AsyncMock,
    ) -> None:
        events: list[ProviderCallEvent] = []
        runner_run.side_effect = [
            _TransientProviderError("internal error", status_code=500),
            _TransientProviderError("still down", status_code=500),
        ]
        settings = _gemini_settings().model_copy(update={"api_max_retries": 1})
        provider = OpenAIAgentsSDKProvider(settings=settings)

        with self.assertRaisesRegex(ProviderCallError, "provider call failed after 2 attempt"):
            asyncio.run(
                provider.run_agent(
                    agent=_stub_agent(),
                    user_input="failing test output",
                    max_turns=2,
                    event_callback=events.append,
                )
            )

        self.assertEqual(runner_run.await_count, 2)
        self.assertEqual(sleep_mock.await_count, 1)
        self.assertEqual(
            [event.event_type for event in events],
            ["retryable_failure", "retry_scheduled", "retries_exhausted"],
        )
        self.assertEqual(events[-1].attempt, 2)
        self.assertEqual(events[-1].status_code, 500)

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

        result = asyncio.run(provider.run_agent(agent=_stub_agent(), user_input="failing test output", max_turns=2))

        self.assertEqual(result.status, "done")
        self.assertEqual(result.changed_files, ["src/a.py"])

    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_rejects_unparseable_output(self, runner_run: AsyncMock) -> None:
        runner_run.return_value = SimpleNamespace(final_output=object())
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())

        with self.assertRaisesRegex(RuntimeError, "invalid structured output"):
            asyncio.run(provider.run_agent(agent=_stub_agent(), user_input="failing test output", max_turns=2))

    def test_create_provider_returns_sdk_adapter(self) -> None:
        provider = create_provider(_gemini_settings())
        self.assertIsInstance(provider, OpenAIAgentsSDKProvider)


class AgentFactoryTests(unittest.TestCase):
    @patch("llm_autofix_agents.llm.agent_factory.Agent")
    def test_build_agent_sets_structured_output_type(self, agent_ctor: AsyncMock) -> None:
        build_agent(
            settings=_gemini_settings(),
            name="test-agent",
            instructions="repair",
            tools=[],
        )

        self.assertTrue(agent_ctor.called)
        output_type = agent_ctor.call_args.kwargs["output_type"]
        self.assertIsInstance(output_type, AgentOutputSchema)
        self.assertIs(output_type.output_type, AgentFixIterationRecord)
        self.assertFalse(output_type.is_strict_json_schema())
        self.assertNotIn("mcp_servers", agent_ctor.call_args.kwargs)

    @patch("llm_autofix_agents.llm.agent_factory.OpenAIChatCompletionsModel")
    @patch("llm_autofix_agents.llm.agent_factory.AsyncOpenAI")
    def test_build_agent_uses_ollama_fallback_api_key(
        self,
        async_openai: AsyncMock,
        model_ctor: AsyncMock,
    ) -> None:
        build_agent(
            settings=LLMSettings(
                provider=ProviderType.OLLAMA,
                model="llama3.1:8b",
                api_key=None,
                base_url="http://localhost:11500/v1",
                max_turns=3,
                tracing_disabled=True,
            ),
            name="test-agent",
            instructions="repair",
            tools=[],
        )

        async_openai.assert_called_once_with(api_key="ollama", base_url="http://localhost:11500/v1")
        self.assertTrue(model_ctor.called)


def _gemini_settings() -> LLMSettings:
    return LLMSettings(
        provider=ProviderType.GEMINI,
        model="gemini-2.5-flash",
        api_key=SecretStr("gemini-key"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        max_turns=3,
        tracing_disabled=True,
    )


def _stub_agent() -> object:
    return object()


class _TransientProviderError(RuntimeError):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


if __name__ == "__main__":
    unittest.main()
