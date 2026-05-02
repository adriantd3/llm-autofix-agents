from __future__ import annotations

import logging
import shutil
import subprocess

from llm_autofix_agents.batch.config import BugEntry, DatasetConfig
from llm_autofix_agents.datasets.base import DatasetPreparationContext, PreparedExecutionCase

logger = logging.getLogger(__name__)


class BugsInPyAdapter:
    type: str = "bugsinpy"

    def prepare_case(
        self,
        context: DatasetPreparationContext,
        bug: BugEntry,
    ) -> PreparedExecutionCase:
        dataset = context.dataset
        host_workspace = context.host_workspace_root / bug.id
        container_workspace = f"{context.container_workspace_root}/{bug.id}"

        if host_workspace.exists():
            shutil.rmtree(host_workspace, ignore_errors=True)
        host_workspace.mkdir(parents=True, exist_ok=True)

        project = bug.metadata.get("project", bug.program or bug.id)
        bug_id = str(bug.metadata.get("bug_id", bug.id))
        version = str(bug.metadata.get("version", "0"))

        try:
            self._checkout(
                dataset, bug, context, container_workspace, project, bug_id, version
            )
            self._compile(dataset, bug, context, container_workspace)
        except Exception:
            shutil.rmtree(host_workspace, ignore_errors=True)
            raise

        test_command = self._resolve_test_command(dataset, bug)

        prompt_variables = {
            "bug_id": bug.id,
            "program": bug.program or project,
            "test": bug.test or "",
            "test_command": test_command,
            "dataset_name": dataset.name,
            "project": project,
            "bug_id_raw": bug_id,
            "version": version,
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
            runner_service="bugsinpy-runner",
        )

    def _checkout(
        self,
        dataset: DatasetConfig,
        bug: BugEntry,
        context: DatasetPreparationContext,
        container_workspace: str,
        project: str,
        bug_id: str,
        version: str,
    ) -> None:
        checkout_template = dataset.tooling.get("checkout_command_template")
        if not checkout_template:
            raise ValueError(
                f"BugsInPy adapter requires dataset.tooling.checkout_command_template for bug '{bug.id}'"
            )
        command = checkout_template.format(
            project=project,
            bug_id=bug_id,
            version=version,
            host_workspace=str(context.host_workspace_root / bug.id),
            container_workspace=container_workspace,
        )
        result = self._run_in_bugsinpy_container(context, command, cwd=container_workspace)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(f"Checkout failed for '{bug.id}': {stderr}")

    def _compile(
        self,
        dataset: DatasetConfig,
        bug: BugEntry,
        context: DatasetPreparationContext,
        container_workspace: str,
    ) -> None:
        compile_command = dataset.tooling.get("compile_command")
        if not compile_command:
            return
        result = self._run_in_bugsinpy_container(context, compile_command, cwd=container_workspace)
        if result.returncode != 0:
            compile_required = dataset.tooling.get("compile_required", True)
            stderr = (result.stderr or "").strip()
            msg = f"Compile command failed for '{bug.id}': {stderr}"
            if compile_required:
                raise RuntimeError(msg)
            logger.warning(msg)

    def _run_in_bugsinpy_container(
        self,
        context: DatasetPreparationContext,
        command: str,
        cwd: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        import os

        uid = os.getuid()
        gid = os.getgid()
        cmd = [
            "docker",
            "compose",
            "-f",
            str(context.compose_file),
            "run",
            "--rm",
            "-T",
            "--user",
            f"{uid}:{gid}",
            "bugsinpy-runner",
            "sh",
            "-c",
        ]
        if cwd:
            wrapped = f"cd {cwd} && {command}"
        else:
            wrapped = command
        cmd.append(wrapped)
        return subprocess.run(
            cmd,
            cwd=str(context.project_dir),
            capture_output=True,
            text=True,
            check=False,
        )

    def _resolve_test_command(self, dataset: DatasetConfig, bug: BugEntry) -> str:
        if bug.test_command is not None:
            return bug.test_command
        test_command = dataset.tooling.get("test_command")
        if test_command:
            return str(test_command)
        return "bugsinpy-test"
