__all__ = [
    "AgentIterationContext",
    "AgentIterationResult",
    "ArchitectureRunner",
    "PatchApplyResult",
    "RunOrchestrator",
    "TestExecution",
    "WorkspaceChangeSet",
]


def __getattr__(name: str):
    if name in {"AgentIterationContext", "AgentIterationResult", "ArchitectureRunner"}:
        from llm_autofix_agents.flow.architecture import AgentIterationContext, AgentIterationResult, ArchitectureRunner

        mapping = {
            "AgentIterationContext": AgentIterationContext,
            "AgentIterationResult": AgentIterationResult,
            "ArchitectureRunner": ArchitectureRunner,
        }
        return mapping[name]
    if name in {"PatchApplyResult", "TestExecution", "WorkspaceChangeSet"}:
        from llm_autofix_agents.flow.models import PatchApplyResult, TestExecution, WorkspaceChangeSet

        mapping = {
            "PatchApplyResult": PatchApplyResult,
            "TestExecution": TestExecution,
            "WorkspaceChangeSet": WorkspaceChangeSet,
        }
        return mapping[name]
    if name == "RunOrchestrator":
        from llm_autofix_agents.flow.orchestrator import RunOrchestrator

        return RunOrchestrator
    raise AttributeError(name)
