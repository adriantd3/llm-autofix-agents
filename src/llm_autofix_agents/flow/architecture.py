from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from llm_autofix_agents.contracts import RunInput
from llm_autofix_agents.llm.provider import AgentFixIterationRecord, LLMProvider
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.observability import RunObserver
from llm_autofix_agents.observability.telemetry import RunTelemetry
from llm_autofix_agents.tools.context import APRToolContext


@dataclass(frozen=True)
class AgentIterationContext:
    """Runtime data needed by an APR architecture to execute one agent step."""

    run_id: str
    iteration_id: str
    iteration_index: int
    run_agent_id: str
    run_input: RunInput
    settings: LLMSettings
    provider: LLMProvider
    agent_context: APRToolContext
    agent_tools: list[object]
    observer: RunObserver
    telemetry: RunTelemetry
    user_input: str
    max_turns: int


@dataclass(frozen=True)
class AgentIterationResult:
    """Runtime-observed result of one architecture step."""

    proposal: AgentFixIterationRecord
    agent_execution_id: str
    started_at: str
    duration_seconds: float
    tool_calls_count: int


class ArchitectureRunner(Protocol):
    """Strategy interface for APR architectures.

    The flow layer owns the lifecycle. Architectures own how agents are composed and
    executed inside one iteration.
    """

    @property
    def architecture_name(self) -> str:
        """Stable architecture name for experiment grouping."""

    @property
    def agent_name(self) -> str:
        """Primary registered agent name for single-agent architectures."""

    @property
    def agent_role(self) -> str:
        """Primary registered agent role for single-agent architectures."""

    @property
    def instructions(self) -> str:
        """Primary instructions hash source for observability."""

    def run_iteration(self, context: AgentIterationContext) -> AgentIterationResult:
        """Execute one architecture iteration."""
