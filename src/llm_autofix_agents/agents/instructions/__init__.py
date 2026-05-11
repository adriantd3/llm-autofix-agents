"""APR agent instructions package.

Each architecture has its own module. Import from here for backwards compatibility:

    from llm_autofix_agents.agents.instructions import MONO_AGENT_APR_INSTRUCTIONS
"""
from __future__ import annotations

from llm_autofix_agents.agents.instructions.handoff import (
    HANDOFF_LOCALIZER_INSTRUCTIONS,
    HANDOFF_PATCHER_INSTRUCTIONS,
    HANDOFF_TRIAGE_INSTRUCTIONS,
    HANDOFF_VALIDATOR_INSTRUCTIONS,
)
from llm_autofix_agents.agents.instructions.mono_agent import MONO_AGENT_APR_INSTRUCTIONS
from llm_autofix_agents.agents.instructions.orchestrator import (
    ORCHESTRATOR_V2_EXPLORER_INSTRUCTIONS,
    ORCHESTRATOR_V2_MAIN_INSTRUCTIONS,
    ORCHESTRATOR_V2_TEST_RUNNER_INSTRUCTIONS,
)
from llm_autofix_agents.agents.instructions.planner_executor import (
    EXECUTOR_INSTRUCTIONS,
    PLANNER_INSTRUCTIONS,
)

__all__ = [
    # mono_agent
    "MONO_AGENT_APR_INSTRUCTIONS",
    # handoff
    "HANDOFF_TRIAGE_INSTRUCTIONS",
    "HANDOFF_LOCALIZER_INSTRUCTIONS",
    "HANDOFF_PATCHER_INSTRUCTIONS",
    "HANDOFF_VALIDATOR_INSTRUCTIONS",
    # orchestrator (v2 task-agents)
    "ORCHESTRATOR_V2_MAIN_INSTRUCTIONS",
    "ORCHESTRATOR_V2_EXPLORER_INSTRUCTIONS",
    "ORCHESTRATOR_V2_TEST_RUNNER_INSTRUCTIONS",
    # planner_executor
    "PLANNER_INSTRUCTIONS",
    "EXECUTOR_INSTRUCTIONS",
]
