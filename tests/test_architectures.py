from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import SecretStr

from llm_autofix_agents.architectures.factory import build_architecture
from llm_autofix_agents.architectures.handoff import build_multi_agent_handoff_architecture
from llm_autofix_agents.architectures.orchestrator import build_multi_agent_orchestrator_architecture
from llm_autofix_agents.llm.settings import LLMSettings, ProviderType


class ArchitectureFactoryTests(unittest.TestCase):
    def test_build_architecture_dispatches_multi_agent_handoff(self) -> None:
        settings = _settings()
        sentinel_architecture = SimpleNamespace(architecture_name="multi_agent_handoff")

        with (
            patch(
                "llm_autofix_agents.architectures.factory.build_multi_agent_handoff_architecture",
                return_value=sentinel_architecture,
            ) as build_handoff,
            patch(
                "llm_autofix_agents.architectures.factory.build_mono_agent_architecture",
            ) as build_mono,
        ):
            architecture = build_architecture(
                strategy="multi_agent_handoff",
                settings=settings,
                agent_models={"triage": "triage-model"},
            )

        self.assertIs(architecture, sentinel_architecture)
        build_handoff.assert_called_once_with(settings=settings, agent_models={"triage": "triage-model"})
        build_mono.assert_not_called()

    def test_build_architecture_dispatches_multi_agent_orchestrator(self) -> None:
        settings = _settings()
        sentinel_architecture = SimpleNamespace(architecture_name="multi_agent_orchestrator")

        with (
            patch(
                "llm_autofix_agents.architectures.factory.build_multi_agent_orchestrator_architecture",
                return_value=sentinel_architecture,
            ) as build_orchestrator,
            patch(
                "llm_autofix_agents.architectures.factory.build_mono_agent_architecture",
            ) as build_mono,
        ):
            architecture = build_architecture(
                strategy="multi_agent_orchestrator",
                settings=settings,
                agent_models={"manager": "manager-model"},
            )

        self.assertIs(architecture, sentinel_architecture)
        build_orchestrator.assert_called_once_with(settings=settings, agent_models={"manager": "manager-model"})
        build_mono.assert_not_called()

    def test_build_architecture_rejects_invalid_strategy(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported architecture strategy"):
            build_architecture(strategy="unknown", settings=_settings())


class MultiAgentHandoffArchitectureTests(unittest.TestCase):
    def test_handoff_architecture_wires_roles_models_and_handoffs(self) -> None:
        settings = _settings()
        tools_by_profile = {
            "minimal": [_tool("read_file"), _tool("search_files")],
            "core": [_tool("read_file"), _tool("execute_command")],
            "full": [_tool("read_file"), _tool("execute_command"), _tool("apply_unified_diff")],
            "triage": [_tool("read_file"), _tool("search_files")],
            "localizer": [_tool("read_file"), _tool("execute_command")],
            "patcher": [_tool("read_file"), _tool("replace_in_file")],
            "validator": [_tool("read_file"), _tool("run_test_target")],
        }
        build_agent_calls: list[dict[str, object]] = []

        def fake_build_agent(**kwargs):
            build_agent_calls.append(kwargs)
            return {"name": kwargs["name"]}

        def fake_handoff(agent, **kwargs):
            return f"handoff:{agent['name']}"

        with (
            patch(
                "llm_autofix_agents.architectures.handoff.build_apr_tools",
                side_effect=lambda profile: list(tools_by_profile[profile]),
            ) as build_tools,
            patch(
                "llm_autofix_agents.architectures.handoff.build_agent",
                side_effect=fake_build_agent,
            ),
            patch(
                "llm_autofix_agents.architectures.handoff.handoff",
                side_effect=fake_handoff,
            ),
        ):
            architecture = build_multi_agent_handoff_architecture(
                settings=settings,
                agent_models={
                    "main": "main-model",
                    "triage": "triage-model",
                    "localizer": "localizer-model",
                    "patcher": "patcher-model",
                    "validator": "validator-model",
                },
            )
            facade_agent = architecture.facade_agent_builder()

        self.assertEqual(architecture.architecture_name, "multi_agent_handoff")
        self.assertEqual(architecture.agent_name, "triage")
        self.assertEqual(architecture.agent_role, "triage")
        self.assertEqual(architecture.agent_model, "triage-model")
        self.assertEqual(architecture.tool_profile, "triage")
        self.assertEqual(architecture.tool_count, 5)
        self.assertEqual(facade_agent, {"name": "triage"})

        self.assertEqual(len(architecture.sub_agents), 3)
        self.assertEqual(architecture.sub_agents[0].agent_name, "localizer")
        self.assertEqual(architecture.sub_agents[1].agent_name, "patcher")
        self.assertEqual(architecture.sub_agents[2].agent_name, "validator")
        self.assertEqual(architecture.sub_agents[0].agent_role, "localizer")
        self.assertEqual(architecture.sub_agents[1].agent_role, "patcher")
        self.assertEqual(architecture.sub_agents[2].agent_role, "validator")

        self.assertEqual(
            [call.args for call in build_tools.call_args_list],
            [
                ("triage",),
                ("localizer",),
                ("patcher",),
                ("validator",),
            ],
        )

        self.assertEqual([call["name"] for call in build_agent_calls], ["validator", "patcher", "localizer", "triage"])
        self.assertEqual(
            [call["model_override"] for call in build_agent_calls],
            [
                "validator-model",
                "patcher-model",
                "localizer-model",
                "triage-model",
            ],
        )
        self.assertIsNone(build_agent_calls[0].get("handoffs"))
        self.assertEqual(build_agent_calls[1]["handoffs"], ["handoff:validator"])
        self.assertEqual(build_agent_calls[2]["handoffs"], ["handoff:patcher"])
        self.assertEqual(build_agent_calls[3]["handoffs"], ["handoff:localizer"])
        self.assertIsNone(build_agent_calls[0].get("output_schema"))
        self.assertIsNone(build_agent_calls[1].get("output_schema"))
        self.assertIsNone(build_agent_calls[2].get("output_schema"))
        self.assertIsNone(build_agent_calls[3].get("output_schema"))


class MultiAgentOrchestratorArchitectureTests(unittest.TestCase):
    def test_orchestrator_architecture_wires_roles_models_and_agent_tools(self) -> None:
        settings = _settings()
        tools_by_profile = {
            "localizer": [_tool("read_file"), _tool("execute_command")],
            "patcher": [_tool("read_file"), _tool("replace_in_file")],
            "validator": [_tool("read_file"), _tool("run_test_target")],
        }
        build_agent_calls: list[dict[str, object]] = []
        as_tool_calls: list[dict[str, object]] = []

        class FakeAgent:
            def __init__(self, **kwargs):
                build_agent_calls.append(kwargs)
                self.name = kwargs["name"]

            def as_tool(self, **kwargs):
                as_tool_calls.append({"agent_name": self.name, **kwargs})
                return f"tool:{self.name}"

        with (
            patch(
                "llm_autofix_agents.architectures.orchestrator.build_apr_tools",
                side_effect=lambda profile: list(tools_by_profile[profile]),
            ) as build_tools,
            patch(
                "llm_autofix_agents.architectures.orchestrator.build_agent",
                side_effect=lambda **kwargs: FakeAgent(**kwargs),
            ),
        ):
            architecture = build_multi_agent_orchestrator_architecture(
                settings=settings,
                agent_models={
                    "main": "main-model",
                    "manager": "manager-model",
                    "localizer": "localizer-model",
                    "patcher": "patcher-model",
                    "validator": "validator-model",
                },
            )
            facade_agent = architecture.facade_agent_builder()

        self.assertEqual(architecture.architecture_name, "multi_agent_orchestrator")
        self.assertEqual(architecture.agent_name, "orchestrator")
        self.assertEqual(architecture.agent_role, "manager")
        self.assertEqual(architecture.agent_model, "manager-model")
        self.assertEqual(architecture.tool_profile, "manager")
        self.assertEqual(architecture.tool_count, 4)
        self.assertEqual(facade_agent.name, "orchestrator")

        self.assertEqual(len(architecture.sub_agents), 3)
        self.assertEqual(architecture.sub_agents[0].agent_name, "localizer")
        self.assertEqual(architecture.sub_agents[1].agent_name, "patcher")
        self.assertEqual(architecture.sub_agents[2].agent_name, "validator")
        self.assertEqual(architecture.sub_agents[0].agent_role, "localizer")
        self.assertEqual(architecture.sub_agents[1].agent_role, "patcher")
        self.assertEqual(architecture.sub_agents[2].agent_role, "validator")

        self.assertEqual(
            [call.args for call in build_tools.call_args_list],
            [
                ("localizer",),
                ("patcher",),
                ("validator",),
            ],
        )

        self.assertEqual(
            [call["name"] for call in build_agent_calls],
            ["localizer", "patcher", "validator", "orchestrator"],
        )
        self.assertEqual(
            [call["model_override"] for call in build_agent_calls],
            [
                "localizer-model",
                "patcher-model",
                "validator-model",
                "manager-model",
            ],
        )

        self.assertIsNone(build_agent_calls[0].get("output_schema"))
        self.assertIsNone(build_agent_calls[1].get("output_schema"))
        self.assertIsNone(build_agent_calls[2].get("output_schema"))
        self.assertEqual(build_agent_calls[3].get("output_schema"), None)

        self.assertEqual(len(as_tool_calls), 3)
        self.assertEqual(as_tool_calls[0]["agent_name"], "localizer")
        self.assertEqual(as_tool_calls[0]["tool_name"], "localize_bug")
        self.assertEqual(as_tool_calls[1]["agent_name"], "patcher")
        self.assertEqual(as_tool_calls[1]["tool_name"], "apply_fix")
        self.assertEqual(as_tool_calls[2]["agent_name"], "validator")
        self.assertEqual(as_tool_calls[2]["tool_name"], "validate_patch")

        self.assertEqual(facade_agent.name, "orchestrator")


def _settings() -> LLMSettings:
    return LLMSettings(
        provider=ProviderType.GEMINI,
        model="gemini-2.5-flash",
        api_key=SecretStr("gemini-key"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        max_turns=3,
        tracing_disabled=True,
    )


def _tool(name: str) -> SimpleNamespace:
    return SimpleNamespace(__name__=name)


if __name__ == "__main__":
    unittest.main()
