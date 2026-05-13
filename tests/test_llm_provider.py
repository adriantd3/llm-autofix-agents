from __future__ import annotations

import asyncio
import json
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
    RunErrorHandlerInput,
    RunErrorHandlerResult,
    _extract_research_context,
    _extract_retry_after_seconds,
    _make_max_turns_handler,
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

    @patch("llm_autofix_agents.llm.provider.asyncio.sleep", new_callable=AsyncMock)
    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_provider_uses_retry_after_header_for_rate_limit(
        self,
        runner_run: AsyncMock,
        sleep_mock: AsyncMock,
    ) -> None:
        # 429 with Retry-After: 45 should sleep for 45s, not the default backoff
        exc = _RateLimitError(status_code=429, retry_after=45.0)
        runner_run.side_effect = [
            exc,
            SimpleNamespace(
                final_output={
                    "status": "done",
                    "reasoning_summary": "Fixed after rate limit",
                    "confidence": 0.8,
                    "changed_files": [],
                }
            ),
        ]
        settings = _gemini_settings().model_copy(
            update={"api_max_retries": 1, "api_retry_max_seconds": 8.0}
        )
        provider = OpenAIAgentsSDKProvider(settings=settings)

        asyncio.run(
            provider.run_agent(agent=_stub_agent(), user_input="test", max_turns=2)
        )

        sleep_mock.assert_awaited_once()
        actual_delay = sleep_mock.await_args.args[0]
        self.assertAlmostEqual(actual_delay, 45.0, places=0)

    def test_extract_retry_after_seconds_reads_header(self) -> None:
        exc = _RateLimitError(status_code=429, retry_after=30.0)
        result = _extract_retry_after_seconds(exc)
        self.assertEqual(result, 30.0)

    def test_extract_retry_after_seconds_returns_none_when_absent(self) -> None:
        exc = _RateLimitError(status_code=429, retry_after=None)
        result = _extract_retry_after_seconds(exc)
        self.assertIsNone(result)

    def test_extract_retry_after_seconds_returns_none_for_non_rate_limit(self) -> None:
        exc = _TransientProviderError("internal error", status_code=500)
        result = _extract_retry_after_seconds(exc)
        self.assertIsNone(result)


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


def _tool_call_item(name: str, args: dict) -> SimpleNamespace:
    return SimpleNamespace(
        type="tool_call_item",
        raw_item=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )


def _tool_output_item(output: str) -> SimpleNamespace:
    return SimpleNamespace(type="tool_call_output_item", output=output)


def _message_item(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        type="message_output_item",
        raw_item=SimpleNamespace(content=[SimpleNamespace(text=text)]),
    )


class RetryContextInjectionTests(unittest.TestCase):
    """Tests that accumulated research context is injected into the retry input."""

    def _success_result(self) -> SimpleNamespace:
        return SimpleNamespace(
            final_output={
                "status": "done",
                "reasoning_summary": "Fixed after retry",
                "confidence": 0.8,
                "changed_files": ["src/a.py"],
            }
        )

    @patch("llm_autofix_agents.llm.provider.asyncio.sleep", new_callable=AsyncMock)
    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_retry_augments_input_when_hooks_have_context(
        self, runner_run: AsyncMock, sleep_mock: AsyncMock
    ) -> None:
        class _HooksWithContext:
            tool_call_count = 5
            agent_execution_id = "ae-1"
            _snapshot = "Search hits:\n  src/foo.py:42 → def buggy\nFiles read: src/foo.py:40-60"
            _reset_calls: list[int] = []

            def extract_context_snapshot(self) -> str:
                return self._snapshot

            def reset_context_snapshot(self) -> None:
                self._reset_calls.append(1)

        hooks = _HooksWithContext()
        runner_run.side_effect = [
            _TransientProviderError("internal error", status_code=500),
            self._success_result(),
        ]
        settings = _gemini_settings().model_copy(update={"api_max_retries": 1})
        provider = OpenAIAgentsSDKProvider(settings=settings)

        asyncio.run(
            provider.run_agent(
                agent=_stub_agent(),
                user_input="original input",
                max_turns=2,
                hooks=hooks,
            )
        )

        self.assertEqual(runner_run.await_count, 2)
        # First call uses original input
        first_call_input = runner_run.call_args_list[0].args[1]
        self.assertEqual(first_call_input, "original input")
        # Second call augments with context
        second_call_input = runner_run.call_args_list[1].args[1]
        self.assertIn("original input", second_call_input)
        self.assertIn("RECOVERY", second_call_input)
        self.assertIn("src/foo.py:42", second_call_input)

    @patch("llm_autofix_agents.llm.provider.asyncio.sleep", new_callable=AsyncMock)
    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_retry_uses_original_input_when_no_context(
        self, runner_run: AsyncMock, sleep_mock: AsyncMock
    ) -> None:
        runner_run.side_effect = [
            _TransientProviderError("internal error", status_code=500),
            self._success_result(),
        ]
        settings = _gemini_settings().model_copy(update={"api_max_retries": 1})
        provider = OpenAIAgentsSDKProvider(settings=settings)

        asyncio.run(
            provider.run_agent(
                agent=_stub_agent(),
                user_input="original input",
                max_turns=2,
                hooks=None,
            )
        )

        second_call_input = runner_run.call_args_list[1].args[1]
        self.assertEqual(second_call_input, "original input")

    @patch("llm_autofix_agents.llm.provider.asyncio.sleep", new_callable=AsyncMock)
    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_retry_resets_snapshot_before_each_attempt(
        self, runner_run: AsyncMock, sleep_mock: AsyncMock
    ) -> None:
        reset_calls: list[int] = []

        class _HooksWithReset:
            tool_call_count = 0
            agent_execution_id = "ae-1"

            def extract_context_snapshot(self) -> str | None:
                return None

            def reset_context_snapshot(self) -> None:
                reset_calls.append(1)

        hooks = _HooksWithReset()
        runner_run.side_effect = [
            _TransientProviderError("error", status_code=500),
            self._success_result(),
        ]
        settings = _gemini_settings().model_copy(update={"api_max_retries": 1})
        provider = OpenAIAgentsSDKProvider(settings=settings)

        asyncio.run(
            provider.run_agent(agent=_stub_agent(), user_input="x", max_turns=2, hooks=hooks)
        )

        # reset_context_snapshot should be called once per attempt (2 attempts)
        self.assertEqual(len(reset_calls), 2)

    @patch("llm_autofix_agents.llm.provider.asyncio.sleep", new_callable=AsyncMock)
    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_retry_scheduled_event_rerun_full_runner_false_when_context_present(
        self, runner_run: AsyncMock, sleep_mock: AsyncMock
    ) -> None:
        events: list[ProviderCallEvent] = []

        class _HooksWithContext:
            tool_call_count = 3
            agent_execution_id = "ae-1"

            def extract_context_snapshot(self) -> str:
                return "Files read: src/foo.py"

            def reset_context_snapshot(self) -> None:
                pass

        runner_run.side_effect = [
            _TransientProviderError("error", status_code=500),
            self._success_result(),
        ]
        settings = _gemini_settings().model_copy(update={"api_max_retries": 1})
        provider = OpenAIAgentsSDKProvider(settings=settings)

        asyncio.run(
            provider.run_agent(
                agent=_stub_agent(),
                user_input="x",
                max_turns=2,
                hooks=_HooksWithContext(),
                event_callback=events.append,
            )
        )

        retry_scheduled = next(e for e in events if e.event_type == "retry_scheduled")
        self.assertFalse(retry_scheduled.rerun_full_runner)

    @patch("llm_autofix_agents.llm.provider.asyncio.sleep", new_callable=AsyncMock)
    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_retry_scheduled_event_rerun_full_runner_true_when_no_context(
        self, runner_run: AsyncMock, sleep_mock: AsyncMock
    ) -> None:
        events: list[ProviderCallEvent] = []
        runner_run.side_effect = [
            _TransientProviderError("error", status_code=500),
            self._success_result(),
        ]
        settings = _gemini_settings().model_copy(update={"api_max_retries": 1})
        provider = OpenAIAgentsSDKProvider(settings=settings)

        asyncio.run(
            provider.run_agent(
                agent=_stub_agent(),
                user_input="x",
                max_turns=2,
                hooks=None,
                event_callback=events.append,
            )
        )

        retry_scheduled = next(e for e in events if e.event_type == "retry_scheduled")
        self.assertTrue(retry_scheduled.rerun_full_runner)


class MaxTurnsHandlerTests(unittest.TestCase):
    def _run_data(self, items: list) -> SimpleNamespace:
        return SimpleNamespace(new_items=items)

    def test_extract_search_hits(self) -> None:
        search_output = json.dumps({
            "ok": True,
            "results": [
                {"path": "youtube_dl/extractor/common.py", "line": 1847, "match": "def _parse_mpd_formats(self,"},
            ],
        })
        items = [
            _tool_call_item("search_files", {"pattern": "def _parse_mpd_formats", "glob": "**/*.py"}),
            _tool_output_item(search_output),
        ]
        notes = _extract_research_context(self._run_data(items), max_turns=20)

        self.assertIn("youtube_dl/extractor/common.py:1847", notes)
        self.assertIn("Search hits", notes)
        self.assertIn("MaxTurnsExceeded after 20 turns", notes)

    def test_extract_files_read_deduplicated(self) -> None:
        items = [
            _tool_call_item("read_file", {"path": "common.py", "start_line": 1847, "end_line": 1900}),
            _tool_output_item(json.dumps({"ok": True, "content": "..."})),
            _tool_call_item("read_file", {"path": "common.py", "start_line": 1847, "end_line": 1900}),
            _tool_output_item(json.dumps({"ok": True, "content": "..."})),
        ]
        notes = _extract_research_context(self._run_data(items), max_turns=10)

        self.assertIn("common.py:1847-1900", notes)
        self.assertEqual(notes.count("common.py:1847-1900"), 1, "should deduplicate repeated reads")

    def test_extract_edit_attempts(self) -> None:
        items = [
            _tool_call_item("replace_in_file", {"path": "common.py"}),
            _tool_output_item(json.dumps({"ok": False, "error": "old_text_not_found"})),
            _tool_call_item("replace_in_file", {"path": "common.py"}),
            _tool_output_item(json.dumps({"ok": True})),
        ]
        notes = _extract_research_context(self._run_data(items), max_turns=15)

        self.assertIn("replace_in_file(common.py) → failed:old_text_not_found", notes)
        self.assertIn("replace_in_file(common.py) → ok", notes)

    def test_extract_last_agent_message(self) -> None:
        items = [
            _message_item("The bug is in the _parse_mpd_formats method, need to add DASH format"),
        ]
        notes = _extract_research_context(self._run_data(items), max_turns=20)

        self.assertIn("_parse_mpd_formats", notes)
        self.assertIn("Last agent reasoning", notes)

    def test_filters_test_file_paths_from_search_hits(self) -> None:
        search_output = json.dumps({
            "ok": True,
            "results": [
                {"path": "test/test_InfoExtractor.py", "line": 498, "match": "'float_duration',"},
                {"path": "tests/test_utils.py", "line": 22, "match": "def test_something"},
                {"path": "youtube_dl/extractor/common.py", "line": 1753, "match": "def _parse_mpd_formats("},
            ],
        })
        items = [
            _tool_call_item("search_files", {"pattern": "_parse_mpd_formats", "glob": "**/*.py"}),
            _tool_output_item(search_output),
        ]
        notes = _extract_research_context(self._run_data(items), max_turns=20)

        self.assertNotIn("test/test_InfoExtractor.py", notes)
        self.assertNotIn("tests/test_utils.py", notes)
        self.assertIn("youtube_dl/extractor/common.py:1753", notes)

    def test_empty_items_fallback(self) -> None:
        notes = _extract_research_context(self._run_data([]), max_turns=20)

        self.assertIn("No tool calls recorded", notes)

    def test_handler_returns_record_with_research_notes(self) -> None:
        search_output = json.dumps({
            "ok": True,
            "results": [{"path": "foo.py", "line": 42, "match": "def buggy_func"}],
        })
        run_data = self._run_data([
            _tool_call_item("search_files", {"pattern": "def buggy_func", "glob": "**/*.py"}),
            _tool_output_item(search_output),
        ])
        handler = _make_max_turns_handler(max_turns=20)
        from agents import MaxTurnsExceeded
        handler_input = SimpleNamespace(
            error=MaxTurnsExceeded("exceeded"),
            context=None,
            run_data=run_data,
        )

        result = handler(handler_input)

        self.assertIsInstance(result, RunErrorHandlerResult)
        self.assertFalse(result.include_in_history)
        proposal = result.final_output
        self.assertIsInstance(proposal, AgentFixIterationRecord)
        self.assertEqual(proposal.status, "done")
        self.assertIn("foo.py:42", proposal.notes or "")

    @patch("llm_autofix_agents.llm.provider.set_tracing_disabled")
    @patch("llm_autofix_agents.llm.provider.Runner.run", new_callable=AsyncMock)
    def test_runner_receives_error_handlers(self, runner_run: AsyncMock, _tracing: AsyncMock) -> None:
        runner_run.return_value = SimpleNamespace(
            final_output=AgentFixIterationRecord(
                status="done", reasoning_summary="ok", confidence=0.9, changed_files=[]
            )
        )
        provider = OpenAIAgentsSDKProvider(settings=_gemini_settings())
        asyncio.run(provider.run_agent(agent=_stub_agent(), user_input="x", max_turns=5))

        _, kwargs = runner_run.call_args
        self.assertIn("error_handlers", kwargs)
        self.assertIn("max_turns", kwargs["error_handlers"])
        self.assertTrue(callable(kwargs["error_handlers"]["max_turns"]))


class _TransientProviderError(RuntimeError):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class _RateLimitError(RuntimeError):
    """Simulates a 429 response with an optional Retry-After header."""

    def __init__(self, *, status_code: int, retry_after: float | None) -> None:
        super().__init__(f"rate limited (status={status_code})")
        self.status_code = status_code
        headers: dict[str, str] = {}
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
        self.response = SimpleNamespace(headers=headers)


if __name__ == "__main__":
    unittest.main()
