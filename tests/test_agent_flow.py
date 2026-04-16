from __future__ import annotations

import unittest
from collections.abc import Sequence

from agents.mcp import MCPServer
from pydantic import SecretStr

from llm_autofix_agents.agent_flow import run_agent_baseline
from llm_autofix_agents.contracts import ErrorCategory, RunInput, RunStatus, StopReason
from llm_autofix_agents.llm.settings import LLMSettings, ProviderType


class AgentFlowTests(unittest.TestCase):
    def test_run_agent_baseline_success(self) -> None:
        provider = _CapturingProvider("suggested fix")
        output = run_agent_baseline(
            RunInput(prompt="Fix parser failure"),
            settings=_settings(),
            provider=provider,
        )

        self.assertEqual(output.status, RunStatus.SUCCESS)
        self.assertEqual(output.stop_reason, StopReason.COMPLETED)
        self.assertEqual(output.final_message, "suggested fix")
        self.assertEqual(output.identity.iteration, 1)
        self.assertIn("stage=agent", output.logs)
        self.assertIn("toolset=mcp-stdio", output.logs)
        self.assertIsNotNone(provider.last_user_input)
        assert provider.last_user_input is not None
        self.assertEqual(provider.last_user_input, "Fix parser failure")
        self.assertIsNotNone(provider.last_mcp_servers)
        assert provider.last_mcp_servers is not None
        self.assertEqual(len(provider.last_mcp_servers), 2)
        self.assertEqual([server.name for server in provider.last_mcp_servers], ["filesystem", "web-search"])

    def test_run_agent_baseline_maps_provider_error(self) -> None:
        output = run_agent_baseline(
            RunInput(prompt="Fix parser failure"),
            settings=_settings(),
            provider=_FailingProvider(),
        )

        self.assertEqual(output.status, RunStatus.FAILED)
        self.assertEqual(output.stop_reason, StopReason.INFRA_FAILURE)
        self.assertEqual(len(output.errors), 1)
        self.assertEqual(output.errors[0].category, ErrorCategory.MODEL)


class _CapturingProvider:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_user_input: str | None = None
        self.last_mcp_servers: list[MCPServer] | None = None

    async def run_prompt(
        self,
        *,
        instructions: str,
        user_input: str,
        max_turns: int,
        tools: Sequence[object] | None = None,
        mcp_servers: Sequence[MCPServer] | None = None,
    ) -> str:
        del instructions, max_turns
        self.last_user_input = user_input
        del tools
        self.last_mcp_servers = list(mcp_servers) if mcp_servers is not None else None
        return self._response


class _FailingProvider:
    async def run_prompt(
        self,
        *,
        instructions: str,
        user_input: str,
        max_turns: int,
        tools: Sequence[object] | None = None,
        mcp_servers: Sequence[MCPServer] | None = None,
    ) -> str:
        del instructions, user_input, max_turns, tools, mcp_servers
        raise RuntimeError("provider down")


def _settings() -> LLMSettings:
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
