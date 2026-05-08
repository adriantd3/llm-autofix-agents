from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llm_autofix_agents.contracts import TestResults
from llm_autofix_agents.flow.models import TestExecution
from llm_autofix_agents.flow.observability_stack import ObservabilityStack
from llm_autofix_agents.flow.workspace.git import TempBranchContext
from llm_autofix_agents.llm.provider import LLMProvider
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.tools.context import APRToolContext


@dataclass
class RunState:
    """Mutable runtime state accumulated across iterations.

    Written by the orchestrator and iteration runner; read by the finalizer.
    All fields that change during execution live here, not in RunConfig.
    """

    # Lifecycle state (written once, at startup or after baseline)
    run_started_monotonic: float = 0.0
    baseline_test_execution: TestExecution | None = None
    temp_branch: TempBranchContext | None = None

    # Token accounting
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0

    # Iteration progress
    max_changed_files_count: int = 0
    accumulated_logs: list[str] = field(default_factory=list)
    final_message: str | None = None
    latest_tests: TestResults | None = None
    latest_diff: str = ""
    latest_artifacts: dict[str, Any] = field(default_factory=dict)
    latest_snapshot: str | None = None
    latest_observed_files: list[str] = field(default_factory=list)

    # Previous-iteration memory for no-progress detection
    previous_proposal_signature: str | None = None
    previous_proposal_status: str | None = None
    previous_proposal_confidence: float | None = None
    previous_test_signature: str | None = None

    # Validation retry state
    validation_feedback: str | None = None
    validation_retries: int = 0


@dataclass(frozen=True)
class RunConfig:
    """Immutable configuration for a single APR run.

    Set once at initialization and never mutated. All state that changes
    during the run lives in RunState. Each component should depend on the
    smallest subset of RunConfig it actually needs.
    """

    # Identity
    run_id: str
    run_agent_id: str
    run_agent_ids: dict[str, str]
    architecture_name: str

    # LLM configuration
    settings: LLMSettings
    provider: LLMProvider

    # Tool configuration
    agent_context: APRToolContext
    tool_profile: str
    tool_count: int

    # Run limits
    max_iterations: int
    test_timeout_seconds: int

    # Workspace
    repo_root: Path

    # Observability (encapsulated — access via cfg.observability.*)
    observability: ObservabilityStack

    # Run metadata for logging and identity
    run_input_metadata: dict[str, Any]
    agent_config: dict[str, Any] = field(default_factory=dict)

    @property
    def results_dir(self) -> Path:
        return self.observability.results_dir(repo_root=self.repo_root, run_id=self.run_id)

