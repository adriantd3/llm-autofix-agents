from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from llm_autofix_agents.batch.config import BugEntry
from llm_autofix_agents.datasets.base import DatasetPreparationContext, PreparedExecutionCase


class QuixBugsAdapter:
    type: str = "quixbugs"

    def prepare_case(
        self,
        context: DatasetPreparationContext,
        bug: BugEntry,
    ) -> PreparedExecutionCase:
        dataset = context.dataset
        if dataset.repository is None:
            raise ValueError(f"QuixBugs adapter requires dataset.repository for bug '{bug.id}'")
        if dataset.repository.branch is None:
            raise ValueError(f"QuixBugs adapter requires dataset.repository.branch for bug '{bug.id}'")

        host_workspace = context.host_workspace_root / bug.id
        container_workspace = f"{context.container_workspace_root}/{bug.id}"

        if host_workspace.exists():
            shutil.rmtree(host_workspace, ignore_errors=True)
        host_workspace.mkdir(parents=True, exist_ok=True)

        try:
            _shallow_clone(dataset.repository.url, dataset.repository.branch, host_workspace)
        except Exception:
            shutil.rmtree(host_workspace, ignore_errors=True)
            raise

        test_command = dataset.resolve_test_command(bug)

        prompt_variables = {
            "bug_id": bug.id,
            "program": bug.program or "",
            "test": bug.test or "",
            "test_command": test_command,
            "dataset_name": dataset.name,
        }

        return PreparedExecutionCase(
            case_id=bug.id,
            dataset_name=dataset.name,
            dataset_type=self.type,
            host_workspace=host_workspace,
            container_workspace=container_workspace,
            test_command=test_command,
            prompt_variables=prompt_variables,
            cleanup_paths=(),
            runner_service="runner",
        )


def _shallow_clone(url: str, branch: str, destination: Path) -> None:
    command = [
        "git",
        "clone",
        "--depth",
        "1",
        "--branch",
        branch,
        url,
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"Failed to clone '{url}' (branch={branch}): {stderr}")
