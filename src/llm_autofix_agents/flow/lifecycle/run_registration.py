from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from llm_autofix_agents.contracts import RunIdentity, RunInput
from llm_autofix_agents.flow.runtime.options import metadata_text
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.observability import (
    AgentDescriptor,
    ModelConfigDescriptor,
    RunDescriptor,
    RunObserver,
    utc_now_iso,
)


@dataclass(frozen=True)
class RunRegistration:
    """Builds and emits observability registration records for a run."""

    architecture_name: str
    agent_name: str
    agent_role: str
    instructions: str

    def start_run(
        self,
        *,
        observer: RunObserver,
        identity: RunIdentity,
        run_input: RunInput,
    ) -> None:
        observer.on_run_started(
            run=RunDescriptor(
                run_id=identity.run_id,
                architecture=self.architecture_name,
                target_repo=run_input.target_repo,
                target_branch=metadata_text(run_input.metadata, "runtime_branch"),
                run_fingerprint=identity.run_fingerprint,
                prompt_hash=sha256(run_input.prompt.encode("utf-8")).hexdigest()[:16],
                benchmark_name=metadata_text(run_input.metadata, "benchmark_name"),
                problem_id=metadata_text(run_input.metadata, "problem_id"),
            ),
            started_at=utc_now_iso(),
        )

    def register_primary_agent(
        self,
        *,
        observer: RunObserver,
        run_id: str,
        settings: LLMSettings,
        tool_profile: str,
    ) -> str | None:
        return observer.on_run_agent_registered(
            run_id=run_id,
            agent=AgentDescriptor(
                agent_name=self.agent_name,
                agent_role=self.agent_role,
                model_config=ModelConfigDescriptor(
                    provider=settings.provider.value,
                    model=settings.model,
                    max_turns=settings.max_turns,
                    base_url=settings.base_url,
                    tracing_disabled=settings.tracing_disabled,
                ),
                tool_profile=tool_profile,
                agent_order=1,
            ),
            instructions_hash=sha256(self.instructions.encode("utf-8")).hexdigest()[:16],
        )
