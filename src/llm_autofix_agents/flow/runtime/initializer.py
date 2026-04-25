from __future__ import annotations

import time
from dataclasses import dataclass

from llm_autofix_agents.contracts import RunInput, build_run_identity
from llm_autofix_agents.flow.architecture import ArchitectureRunner
from llm_autofix_agents.flow.lifecycle.observer_factory import build_observer
from llm_autofix_agents.flow.lifecycle.run_registration import RunRegistration
from llm_autofix_agents.flow.runtime.context import RunConfig, RunState
from llm_autofix_agents.flow.workspace.state import load_ignore_rules, resolve_repo_root
from llm_autofix_agents.llm.provider import LLMProvider
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.observability import (
    resolve_observability_config,
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
    ) -> tuple[RunConfig, RunState]:
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

        registration = RunRegistration(
            architecture_name=self.architecture.architecture_name,
            agent_name=self.architecture.agent_name,
            agent_role=self.architecture.agent_role,
            instructions=self.architecture.instructions,
        )
        registration.start_run(observer=observer, identity=identity, run_input=run_input)
        run_agent_id = registration.register_primary_agent(
            observer=observer,
            run_id=identity.run_id,
            settings=settings,
            tool_profile=tool_profile,
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

        return cfg, RunState()
