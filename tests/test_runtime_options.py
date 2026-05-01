from __future__ import annotations

import unittest

from llm_autofix_agents.flow.runtime.options import resolve_architecture


class RuntimeOptionsTests(unittest.TestCase):
    def test_resolve_architecture_defaults_to_mono(self) -> None:
        self.assertEqual(resolve_architecture({}), "mono_agent")

    def test_resolve_architecture_uses_metadata(self) -> None:
        self.assertEqual(
            resolve_architecture({"runtime_architecture": "multi_agent_handoff"}),
            "multi_agent_handoff",
        )

    def test_resolve_architecture_prefers_explicit(self) -> None:
        self.assertEqual(
            resolve_architecture(
                {"runtime_architecture": "mono_agent"},
                explicit="multi_agent_handoff",
            ),
            "multi_agent_handoff",
        )

    def test_resolve_architecture_rejects_invalid_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "runtime_architecture must be a string"):
            resolve_architecture({"runtime_architecture": 123})

    def test_resolve_architecture_rejects_invalid_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported architecture strategy"):
            resolve_architecture({"runtime_architecture": "mono-agent"})


if __name__ == "__main__":
    unittest.main()
