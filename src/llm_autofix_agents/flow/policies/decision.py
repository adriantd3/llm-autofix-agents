from __future__ import annotations

from llm_autofix_agents.contracts import RunInput
from llm_autofix_agents.flow.models import IterationDecision, IterationObservation
from llm_autofix_agents.flow.policies.stop import StopPolicy
from llm_autofix_agents.flow.policies.validation import IterationValidationResult
from llm_autofix_agents.flow.runtime.context import RunState


def decide_iteration_outcome(
    *,
    observation: IterationObservation,
    validation: IterationValidationResult,
    state: RunState,
    run_input: RunInput,
    stop_policy: StopPolicy,
) -> IterationDecision:
    """Pure function: maps observation + validation → iteration decision. No side effects."""
    proposal = observation.proposal
    test_execution = observation.test_execution
    changed_files = observation.changes.tracked_changed_files

    if not validation.ok:
        if validation.retryable and state.validation_retries < 1:
            return IterationDecision(
                action="retry",
                log_suffix=f"validation_result={validation.failure_type}_retryable",
            )
        return IterationDecision(
            action="stop_validation_failure",
            log_suffix=f"validation_result={validation.failure_type}",
        )

    if stop_policy.no_progress(
        state=state,
        proposal=proposal,
        test_execution=test_execution,
        changed_files=changed_files,
    ):
        return IterationDecision(action="stop_no_progress")

    if stop_policy.success(
        run_input=run_input,
        proposal=proposal,
        test_execution=test_execution,
        changed_files=changed_files,
    ):
        return IterationDecision(action="stop_success")

    if stop_policy.agent_reported_stuck(proposal):
        return IterationDecision(
            action="stop_agent_stuck",
            log_suffix="iteration_result=agent_reported_stuck",
        )

    return IterationDecision(action="continue")
