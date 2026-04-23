from __future__ import annotations

import unittest

from llm_autofix_agents.toolset import (
    APR_CORE_TOOLS,
    APR_FUNCTION_TOOLS,
    APR_SAFE_MINIMAL_TOOLS,
    build_apr_tools,
)


class APRToolsetBuilderTests(unittest.TestCase):
    def test_build_apr_tools_defaults_to_full_profile(self) -> None:
        tools = build_apr_tools()

        self.assertEqual(len(tools), len(APR_FUNCTION_TOOLS))
        self.assertEqual({tool.name for tool in tools}, {tool.name for tool in APR_FUNCTION_TOOLS})

    def test_build_apr_tools_core_profile(self) -> None:
        tools = build_apr_tools("core")

        self.assertEqual(len(tools), len(APR_CORE_TOOLS))
        self.assertEqual([tool.name for tool in tools], [tool.name for tool in APR_CORE_TOOLS])

    def test_build_apr_tools_minimal_profile(self) -> None:
        tools = build_apr_tools("minimal")

        self.assertEqual(len(tools), len(APR_SAFE_MINIMAL_TOOLS))
        self.assertEqual([tool.name for tool in tools], [tool.name for tool in APR_SAFE_MINIMAL_TOOLS])

    def test_build_apr_tools_rejects_unknown_profile(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown APR tool profile"):
            build_apr_tools("web-search")


if __name__ == "__main__":
    unittest.main()
