from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents.mcp import MCPServerStdio

from llm_autofix_agents.toolset import (
    DEFAULT_FILESYSTEM_MCP_PACKAGE,
    DEFAULT_SHELL_MCP_PACKAGE,
    DEFAULT_WEB_SEARCH_MCP_PACKAGE,
    build_mcp_servers,
)


class MCPServerBuilderTests(unittest.TestCase):
    def test_build_mcp_servers_defaults_to_filesystem_shell_and_web_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir).resolve()
            servers = build_mcp_servers(target_repo=tmp_dir, env={})

            self.assertEqual([server.name for server in servers], ["filesystem", "shell", "web-search"])
            self.assertTrue(all(isinstance(server, MCPServerStdio) for server in servers))

            filesystem_server = servers[0]
            self.assertEqual(filesystem_server.params.command, "npx")
            self.assertEqual(
                filesystem_server.params.args,
                ["-y", DEFAULT_FILESYSTEM_MCP_PACKAGE, str(repo_root)],
            )

            shell_server = servers[1]
            self.assertEqual(shell_server.params.command, "npx")
            self.assertEqual(shell_server.params.args, ["-y", DEFAULT_SHELL_MCP_PACKAGE])

            web_search_server = servers[2]
            self.assertEqual(web_search_server.params.command, "npx")
            self.assertEqual(web_search_server.params.args, ["-y", DEFAULT_WEB_SEARCH_MCP_PACKAGE])

    def test_build_mcp_servers_supports_web_search_opt_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            servers = build_mcp_servers(
                target_repo=tmp_dir,
                env={
                    "WEB_SEARCH_MCP_ENABLED": "false",
                },
            )

            self.assertEqual([server.name for server in servers], ["filesystem", "shell"])

    def test_build_mcp_servers_supports_web_search_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            entrypoint = "C:/mcp/web-search-mcp/dist/index.js"
            servers = build_mcp_servers(
                target_repo=tmp_dir,
                env={
                    "WEB_SEARCH_MCP_ENTRYPOINT": entrypoint,
                },
            )

            web_search_server = servers[2]
            self.assertEqual(web_search_server.params.command, "node")
            self.assertEqual(web_search_server.params.args, [entrypoint])

    def test_build_mcp_servers_supports_shell_mcp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            servers = build_mcp_servers(
                target_repo=tmp_dir,
                env={
                    "SHELL_MCP_ENABLED": "true",
                    "WEB_SEARCH_MCP_ENABLED": "false",
                },
            )

            self.assertEqual([server.name for server in servers], ["filesystem", "shell"])
            shell_server = servers[1]
            self.assertEqual(shell_server.params.command, "npx")
            self.assertEqual(shell_server.params.args, ["-y", DEFAULT_SHELL_MCP_PACKAGE])

    def test_build_mcp_servers_supports_shell_custom_command_and_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            servers = build_mcp_servers(
                target_repo=tmp_dir,
                env={
                    "SHELL_MCP_ENABLED": "true",
                    "SHELL_MCP_COMMAND": "node",
                    "SHELL_MCP_ARGS_JSON": '["C:/mcp/shell/dist/index.js"]',
                    "SHELL_MCP_ENV_JSON": '{"SHELL_MODE":"restricted"}',
                },
            )

            shell_server = servers[1]
            self.assertEqual(shell_server.params.command, "node")
            self.assertEqual(shell_server.params.args, ["C:/mcp/shell/dist/index.js"])
            self.assertEqual(shell_server.params.env, {"SHELL_MODE": "restricted"})

    def test_build_mcp_servers_respects_disable_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            servers = build_mcp_servers(
                target_repo=tmp_dir,
                env={
                    "FILESYSTEM_MCP_ENABLED": "false",
                    "SHELL_MCP_ENABLED": "true",
                    "WEB_SEARCH_MCP_ENABLED": "false",
                },
            )

            self.assertEqual([server.name for server in servers], ["shell"])

    def test_build_mcp_servers_rejects_invalid_boolean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaisesRegex(ValueError, "Invalid boolean value"):
                build_mcp_servers(
                    target_repo=tmp_dir,
                    env={
                        "FILESYSTEM_MCP_ENABLED": "sometimes",
                    },
                )

    def test_build_mcp_servers_rejects_missing_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_repo = Path(tmp_dir) / "does-not-exist"
            with self.assertRaisesRegex(ValueError, "target repo does not exist"):
                build_mcp_servers(target_repo=str(missing_repo), env={})


if __name__ == "__main__":
    unittest.main()
