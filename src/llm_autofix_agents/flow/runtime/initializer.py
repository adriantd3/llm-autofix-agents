from __future__ import annotations

import time
from dataclasses import dataclass
from hashlib import sha256

from llm_autofix_agents.contracts import RunInput, build_run_identity
from llm_autofix_agents.flow.architecture import ArchitectureRunner
from llm_autofix_agents.flow.lifecycle.observer_factory import build_observer
from llm_autofix_agents.flow.runtime.context import RunConfig, RunState
from llm_autofix_agents.flow.runtime.options import metadata_text
from llm_autofix_agents.flow.workspace.state import load_ignore_rules, resolve_repo_root
from llm_autofix_agents.llm.provider import LLMProvider
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.observability import (
    AgentDescriptor,
    ModelConfigDescriptor,
    RunDescriptor,
    resolve_observability_config,
    utc_now_iso,
)
from llm_autofix_agents.tools import APRToolContext, build_apr_tools


@dataclass(frozen=True)
class RunInitializer:
    """Builds initial runtime state and emits run-start lifecycle events."""

    architecture: ArchitectureRunner

    def initialize(
        self,
        *,
        run_input: RunInput,
        settings: LLMSettings,
        provider: LLMProvider,
        tool_profile: str,
        max_iterations: int,
        test_timeout_seconds: int,
    ) -> tuple[RunState, RunConfig]:
        repo_root = resolve_repo_root(run_input.target_repo)
        agent_config = {
            **settings.fingerprint_payload(),
            "architecture": self.architecture.architecture_name,
            "tool_profile": tool_profile,
        }
        identity = build_run_identity(run_input=run_input, agent_config=agent_config, iteration=1)

        observer, sqlite_store, live_observer = build_observer(
            config=resolve_observability_config(repo_root=repo_root, metadata=run_input.metadata),
            repo_root=repo_root,
            run_id=identity.run_id,
            architecture_name=self.architecture.architecture_name,
        )

        observer.on_run_started(
            run=RunDescriptor(
                run_id=identity.run_id,
                architecture=self.architecture.architecture_name,
                target_repo=run_input.target_repo,
                target_branch=metadata_text(run_input.metadata, "runtime_branch"),
                run_fingerprint=identity.run_fingerprint,
                prompt_hash=sha256(run_input.prompt.encode("utf-8")).hexdigest()[:16],
                benchmark_name=metadata_text(run_input.metadata, "benchmark_name"),
                problem_id=metadata_text(run_input.metadata, "problem_id"),
            ),
            started_at=utc_now_iso(),
        )

        run_agent_id = observer.on_run_agent_registered(
            run_id=identity.run_id,
            agent=AgentDescriptor(
                agent_name=self.architecture.agent_name,
                agent_role=self.architecture.agent_role,
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
            instructions_hash=sha256(self.architecture.instructions.encode("utf-8")).hexdigest()[:16],
        )

        cfg = RunConfig(
            run_id=identity.run_id,
            run_agent_id=run_agent_id or f"{identity.run_id}-agent-{self.architecture.agent_name}",
            architecture_name=self.architecture.architecture_name,
            instructions=self.architecture.instructions,
            settings=settings,
            provider=provider,
            agent_context=APRToolContext(root_dir=str(repo_root)),
            agent_tools=build_apr_tools(tool_profile),
            tool_profile=tool_profile,
            max_iterations=max_iterations,
            test_timeout_seconds=test_timeout_seconds,
            repo_root=repo_root,
            test_command=run_input.test_command,
            ignore_rules=load_ignore_rules(repo_root),
            observer=observer,
            sqlite_store=sqlite_store,
            live_observer=live_observer,
            run_input_metadata=run_input.metadata,
            agent_config=agent_config,
            run_started_monotonic=time.perf_counter(),
        )

        return RunState(), cfg
