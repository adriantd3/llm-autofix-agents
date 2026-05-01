from __future__ import annotations

import time
from dataclasses import dataclass

from llm_autofix_agents.architectures.config import BuiltArchitecture
from llm_autofix_agents.contracts import RunInput, build_run_identity
from llm_autofix_agents.flow.lifecycle.observer_factory import build_observer
from llm_autofix_agents.flow.runtime.context import RunConfig, RunState
from llm_autofix_agents.flow.runtime.options import metadata_text
from llm_autofix_agents.flow.workspace.state import resolve_repo_root
from llm_autofix_agents.llm.provider import LLMProvider
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.observability import (
    resolve_observability_config,
)
from llm_autofix_agents.observability.telemetry import RunTelemetry
from llm_autofix_agents.tools.context import APRToolContext


@dataclass(frozen=True)
class RunInitializer:
    """Builds initial runtime state and emits run-start lifecycle events."""

    architecture: BuiltArchitecture

    def initialize(
        self,
        *,
        run_input: RunInput,
        settings: LLMSettings,
        provider: LLMProvider,
        max_iterations: int,
        test_timeout_seconds: int,
    ) -> tuple[RunConfig, RunState]:
        repo_root = resolve_repo_root(run_input.target_repo)
        resolved_model = self.architecture.agent_model or settings.model
        agent_config = {
            **settings.fingerprint_payload(),
            "architecture": self.architecture.architecture_name,
            "agent_name": self.architecture.agent_name,
            "agent_role": self.architecture.agent_role,
            "tool_profile": self.architecture.tool_profile,
            "tool_count": self.architecture.tool_count,
        }
        agent_config["model"] = resolved_model
        identity = build_run_identity(run_input=run_input, agent_config=agent_config, iteration=1)

        observer, sqlite_store, live_observer = build_observer(
            config=resolve_observability_config(repo_root=repo_root, metadata=run_input.metadata),
            repo_root=repo_root,
            run_id=identity.run_id,
            architecture_name=self.architecture.architecture_name,
        )
        telemetry = RunTelemetry(observer=observer, run_id=identity.run_id)
        telemetry.start_run(
            architecture=self.architecture.architecture_name,
            target_repo=run_input.target_repo,
            target_branch=metadata_text(run_input.metadata, "runtime_branch"),
            run_fingerprint=identity.run_fingerprint,
            prompt=run_input.prompt,
            benchmark_name=metadata_text(run_input.metadata, "benchmark_name"),
            problem_id=metadata_text(run_input.metadata, "problem_id"),
        )
        run_agent_id = telemetry.register_agent(
            agent_name=self.architecture.agent_name,
            agent_role=self.architecture.agent_role,
            provider=settings.provider.value,
            model=resolved_model,
            max_turns=settings.max_turns,
            tool_profile=self.architecture.tool_profile,
            instructions=self.architecture.instructions,
            base_url=settings.base_url,
            tracing_disabled=settings.tracing_disabled,
            agent_order=1,
        )
        run_agent_ids: dict[str, str] = {self.architecture.agent_name: run_agent_id}

        for order, sub in enumerate(self.architecture.sub_agents, start=2):
            sub_model = sub.model or resolved_model
            sub_run_agent_id = telemetry.register_agent(
                agent_name=sub.agent_name,
                agent_role=sub.agent_role,
                provider=settings.provider.value,
                model=sub_model,
                max_turns=settings.max_turns,
                tool_profile=sub.tool_profile,
                instructions=sub.instructions,
                base_url=settings.base_url,
                tracing_disabled=settings.tracing_disabled,
                agent_order=order,
            )
            run_agent_ids[sub.agent_name] = sub_run_agent_id

        cfg = RunConfig(
            run_id=identity.run_id,
            run_agent_id=run_agent_id,
            run_agent_ids=run_agent_ids,
            architecture_name=self.architecture.architecture_name,
            settings=settings,
            provider=provider,
            facade_agent_builder=self.architecture.facade_agent_builder,
            agent_context=APRToolContext(root_dir=str(repo_root)),
            tool_profile=self.architecture.tool_profile,
            tool_count=self.architecture.tool_count,
            max_iterations=max_iterations,
            test_timeout_seconds=test_timeout_seconds,
            repo_root=repo_root,
            telemetry=telemetry,
            sqlite_store=sqlite_store,
            live_observer=live_observer,
            run_input_metadata=run_input.metadata,
            agent_config=agent_config,
            run_started_monotonic=time.perf_counter(),
        )

        return cfg, RunState()
