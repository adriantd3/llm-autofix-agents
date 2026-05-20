from __future__ import annotations

from dataclasses import dataclass, field

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
    iteration_edit_count: int = 0
    # Incremented by lifecycle hooks on every tool call; used by dynamic
    # instructions to detect agents that explore without ever editing.
    iteration_tool_call_count: int = 0
    # Exit code of the baseline test run — set once before the first iteration
    # and preserved across iterations. Used to tailor tool guards and facade
    # context (e.g. exit_code=4 is a collection failure, not a code bug).
    baseline_exit_code: int | None = None
    # Number of run_test_target calls made before any code edit in the current
    # iteration. Reset each iteration alongside iteration_edit_count.
    pre_edit_test_count: int = 0
    # Hard limit on search_files calls while no edit has been made.
    # Mirrors the run_test_target guard: once the budget is exhausted the tool
    # returns an error so the model is forced to either apply a fix or report
    # stuck — rather than looping on search variations indefinitely.
    # 0 = no limit. Reset each iteration.
    search_files_budget: int = 8
    search_files_calls: int = 0
    # Tracks (lower-cased pattern, glob) pairs searched this iteration to
    # short-circuit exact duplicate calls. Maps query key -> call number.
    # Reset each iteration.
    seen_search_queries: dict[str, int] = field(default_factory=dict)


def get_tool_context(wrapper: RunContextWrapper[APRToolContext]) -> APRToolContext:
    return wrapper.context
