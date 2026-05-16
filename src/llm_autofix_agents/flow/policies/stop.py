from __future__ import annotations

from dataclasses import dataclass

from llm_autofix_agents.contracts import RunInput
from llm_autofix_agents.flow.models import TestExecution
from llm_autofix_agents.flow.policies.iteration import is_no_progress, proposal_signature
from llm_autofix_agents.flow.runtime.context import RunState
from llm_autofix_agents.llm.provider import AgentFixIterationRecord


@dataclass(frozen=True)
class StopPolicy:
    """Stop policy for the baseline APR lifecycle."""

    def success(
        self,
        *,
        run_input: RunInput,
        proposal: AgentFixIterationRecord,
        test_execution: TestExecution,
        changed_files: list[str],
    ) -> bool:
        # Observable success: tests pass AND files were changed.
        # This takes precedence over agent-reported status because test results
        # and file changes are ground truth; the agent may return text or
        # an incorrect status when it fails to produce structured output.
        if run_input.test_command is not None:
            tests_pass = test_execution.exit_code == 0 and not test_execution.timed_out
            if tests_pass and changed_files:
                return True
        # Agent-reported success (fallback when no test command or no files changed).
        if proposal.proposal.status != "done":
            return False
        if run_input.test_command is None:
            return True
        return test_execution.exit_code == 0 and not test_execution.timed_out

    def no_progress(
        self,
        *,
        state: RunState,
        proposal: AgentFixIterationRecord,
        test_execution: TestExecution,
        changed_files: list[str],
    ) -> bool:
        return is_no_progress(
            previous_message=state.previous_proposal_signature,
            current_message=proposal_signature(proposal),
            previous_status=state.previous_proposal_status,
            current_status=proposal.proposal.status,
            previous_confidence=state.previous_proposal_confidence,
            current_confidence=proposal.proposal.confidence,
            previous_test_signature=state.previous_test_signature,
            current_test_signature=test_execution.signature,
            changed_files=changed_files,
        )

    def agent_reported_stuck(self, proposal: AgentFixIterationRecord) -> bool:
        return proposal.proposal.status == "stuck"
