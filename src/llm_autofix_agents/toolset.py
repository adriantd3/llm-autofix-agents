from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Final, cast

from agents.mcp import MCPServer, MCPServerStdio, MCPServerStdioParams

DEFAULT_FILESYSTEM_MCP_COMMAND: Final[str] = "npx"
DEFAULT_FILESYSTEM_MCP_PACKAGE: Final[str] = "@modelcontextprotocol/server-filesystem"
DEFAULT_WEB_SEARCH_MCP_COMMAND: Final[str] = "npx"
DEFAULT_WEB_SEARCH_MCP_PACKAGE: Final[str] = "web-search-mcp"
DEFAULT_SHELL_MCP_COMMAND: Final[str] = "npx"
DEFAULT_SHELL_MCP_PACKAGE: Final[str] = "mcp-shell-server"


def build_mcp_servers(*, target_repo: str | None, env: Mapping[str, str] | None = None) -> list[MCPServer]:
    values = dict(env) if env is not None else dict(os.environ)
    repo_root = _resolve_repo_root(target_repo)

    servers: list[MCPServer] = []
    if _parse_bool(values.get("FILESYSTEM_MCP_ENABLED"), default=True):
        servers.append(_build_filesystem_server(repo_root=repo_root, env=values))
    if _parse_bool(values.get("SHELL_MCP_ENABLED"), default=True):
        servers.append(_build_shell_server(env=values))
    if _parse_bool(values.get("WEB_SEARCH_MCP_ENABLED"), default=True):
        servers.append(_build_web_search_server(env=values))
    return servers


def _build_filesystem_server(*, repo_root: Path, env: Mapping[str, str]) -> MCPServerStdio:
    command = _normalize_required_text(
        env.get("FILESYSTEM_MCP_COMMAND", DEFAULT_FILESYSTEM_MCP_COMMAND),
        env_var="FILESYSTEM_MCP_COMMAND",
    )
    args = _parse_optional_list(env.get("FILESYSTEM_MCP_ARGS_JSON"))
    if args is None:
        package_name = _normalize_required_text(
            env.get("FILESYSTEM_MCP_PACKAGE", DEFAULT_FILESYSTEM_MCP_PACKAGE),
            env_var="FILESYSTEM_MCP_PACKAGE",
        )
        args = ["-y", package_name, str(repo_root)]

    return MCPServerStdio(
        params={
            "command": command,
            "args": args,
        },
        name="filesystem",
        cache_tools_list=True,
    )


def _build_web_search_server(*, env: Mapping[str, str]) -> MCPServerStdio:
    configured_command = env.get("WEB_SEARCH_MCP_COMMAND")
    command = _normalize_optional_text(configured_command)

    args = _parse_optional_list(env.get("WEB_SEARCH_MCP_ARGS_JSON"))
    if args is None:
        entrypoint = _normalize_optional_text(env.get("WEB_SEARCH_MCP_ENTRYPOINT"))
        if entrypoint is not None:
            args = [entrypoint]
            if command is None:
                command = "node"
        else:
            package_name = _normalize_required_text(
                env.get("WEB_SEARCH_MCP_PACKAGE", DEFAULT_WEB_SEARCH_MCP_PACKAGE),
                env_var="WEB_SEARCH_MCP_PACKAGE",
            )
            args = ["-y", package_name]

    resolved_command = command if command is not None else DEFAULT_WEB_SEARCH_MCP_COMMAND
    server_env = _parse_optional_mapping(env.get("WEB_SEARCH_MCP_ENV_JSON"))
    params: MCPServerStdioParams = {
        "command": resolved_command,
        "args": args,
    }
    if server_env is not None:
        params["env"] = server_env

    return MCPServerStdio(
        params=params,
        name="web-search",
        cache_tools_list=True,
    )


def _build_shell_server(*, env: Mapping[str, str]) -> MCPServerStdio:
    command = _normalize_required_text(
        env.get("SHELL_MCP_COMMAND", DEFAULT_SHELL_MCP_COMMAND),
        env_var="SHELL_MCP_COMMAND",
    )
    args = _parse_optional_list(env.get("SHELL_MCP_ARGS_JSON"))
    if args is None:
        package_name = _normalize_required_text(
            env.get("SHELL_MCP_PACKAGE", DEFAULT_SHELL_MCP_PACKAGE),
            env_var="SHELL_MCP_PACKAGE",
        )
        args = ["-y", package_name]

    server_env = _parse_optional_mapping(env.get("SHELL_MCP_ENV_JSON"))
    params: MCPServerStdioParams = {
        "command": command,
        "args": args,
    }
    if server_env is not None:
        params["env"] = server_env

    return MCPServerStdio(
        params=params,
        name="shell",
        cache_tools_list=True,
    )


def _resolve_repo_root(target_repo: str | None) -> Path:
    repo_root = Path(target_repo if target_repo else ".").resolve()
    if not repo_root.exists():
        raise ValueError(f"target repo does not exist: {repo_root}")
    if not repo_root.is_dir():
        raise ValueError(f"target repo is not a directory: {repo_root}")
    return repo_root


def _normalize_required_text(value: str | None, *, env_var: str) -> str:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        raise ValueError(f"{env_var} cannot be empty")
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if not normalized:
        return default
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _parse_optional_list(value: str | None) -> list[str] | None:
    parsed = _parse_optional_json(value)
    if parsed is None:
        return None
    if not isinstance(parsed, list):
        raise ValueError("Expected a JSON list")
    rendered: list[str] = []
    for item in parsed:
        if not isinstance(item, str):
            raise ValueError("Expected all JSON list entries to be strings")
        normalized = item.strip()
        if not normalized:
            raise ValueError("JSON list entries cannot be empty")
        rendered.append(normalized)
    return rendered


def _parse_optional_mapping(value: str | None) -> dict[str, str] | None:
    parsed = _parse_optional_json(value)
    if parsed is None:
        return None
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object")

    rendered: dict[str, str] = {}
    for key, entry in parsed.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Expected non-empty string keys in JSON object")
        if not isinstance(entry, str):
            raise ValueError("Expected string values in JSON object")
        rendered[key] = entry
    return rendered


def _parse_optional_json(value: str | None) -> object | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    try:
        return cast(object, json.loads(normalized))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON value: {value}") from exc
