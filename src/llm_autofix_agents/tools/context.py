from __future__ import annotations

from dataclasses import dataclass

from agents import RunContextWrapper


@dataclass
class APRToolContext:
    """Runtime configuration for APR filesystem tools."""

    root_dir: str
    max_read_chars: int = 12_000
    max_search_hits: int = 50
    max_cmd_output_chars: int = 12_000
    max_file_bytes: int = 512_000
    max_list_entries: int = 400
    default_test_timeout_seconds: int = 120


def get_tool_context(wrapper: RunContextWrapper[APRToolContext]) -> APRToolContext:
    return wrapper.context
