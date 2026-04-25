from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llm_autofix_agents.contracts import TestResults
from llm_autofix_agents.flow.models import TestExecution
from llm_autofix_agents.flow.workspace.git import TempBranchContext
from llm_autofix_agents.llm.provider import LLMProvider
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.observability import MarkdownLiveObserver, RunObserver, SQLiteObservabilityStore
from llm_autofix_agents.observability.telemetry import RunTelemetry
from llm_autofix_agents.tools.context import APRToolContext


@dataclass
class RunState:
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    max_changed_files_count: int = 0
    accumulated_logs: list[str] = field(default_factory=list)
    final_message: str | None = None
    latest_tests: TestResults | None = None
    latest_diff: str = ""
    latest_artifacts: dict[str, Any] = field(default_factory=dict)
    latest_proposal_changed_files: list[str] = field(default_factory=list)
    latest_changed_files: list[str] = field(default_factory=list)
    previous_proposal_signature: str | None = None
    previous_proposal_status: str | None = None
    previous_proposal_confidence: float | None = None
    previous_test_signature: str | None = None


@dataclass
class RunConfig:
    run_id: str
    run_agent_id: str
    architecture_name: str
    instructions: str
    settings: LLMSettings
    provider: LLMProvider
    agent_context: APRToolContext
    agent_tools: list[object]
    tool_profile: str
    max_iterations: int
    test_timeout_seconds: int
    repo_root: Path
    test_command: str | None
    ignore_rules: list[str]
    observer: RunObserver
    telemetry: RunTelemetry
    sqlite_store: SQLiteObservabilityStore | None
    live_observer: MarkdownLiveObserver | None
    run_input_metadata: dict[str, Any]
    agent_config: dict[str, Any] = field(default_factory=dict)
    run_started_monotonic: float = 0.0
    baseline_test_execution: TestExecution | None = None
    temp_branch: TempBranchContext | None = None
