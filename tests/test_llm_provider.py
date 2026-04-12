from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pydantic import SecretStr

from llm_autofix_agents.config import LLMSettings, ProviderType
from llm_autofix_agents.llm_provider import OpenAIAgentsSDKProvider, create_provider


class LLMProviderTests(unittest.TestCase):
    @patch("llm_autofix_agents.llm_provider.set_tracing_disabled")
    @patch("llm_autofix_agents.llm_provider.Runner.run", new_callable=AsyncMock)
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

    @patch("llm_autofix_agents.llm_provider.Runner.run", new_callable=AsyncMock)
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

    @patch("llm_autofix_agents.llm_provider.Runner.run", new_callable=AsyncMock)
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
