from __future__ import annotations

import logging
import shlex
import shutil
import subprocess
from pathlib import Path

from llm_autofix_agents.batch.config import BugEntry, DatasetConfig
from llm_autofix_agents.datasets.base import DatasetPreparationContext, PreparedExecutionCase

logger = logging.getLogger(__name__)


class BugsInPyAdapter:
    """Adapter for BugsInPy dataset.

    Current limitation: the BugsInPy runner supports only bugs compatible with
    the Python version installed in docker/bugsinpy.Dockerfile.
    Future work: select runner images by BugsInPy python_version.
    """

    type: str = "bugsinpy"

    # Files expected after a successful checkout
    _CHECKOUT_REQUIRED_FILES = (
        ".git",
        "bugsinpy_bug.info",
        "bugsinpy_requirements.txt",
        "bugsinpy_run_test.sh",
    )

    # Files expected after a successful compile
    # env/bin/python is a symlink to /usr/local/bin/python3 (inside Docker) — broken on host.
    # env/bin/activate is a regular shell script; its presence confirms the venv was compiled.
    _COMPILE_REQUIRED_FILES = (
        "bugsinpy_compile_flag",
        "env/bin/activate",
    )

    def prepare_case(
        self,
        context: DatasetPreparationContext,
        bug: BugEntry,
    ) -> PreparedExecutionCase:
        dataset = context.dataset
        project = bug.metadata.get("project", bug.program or bug.id)
        bug_id = str(bug.metadata.get("bug_id", bug.id))
        version = str(bug.metadata.get("version", "0"))

        # BugsInPy checkout creates <work_dir>/<project>, not <work_dir>.
        host_case_root = context.host_workspace_root / bug.id
        container_case_root = f"{context.container_workspace_root}/{bug.id}"

        host_project_workspace = host_case_root / project
        container_project_workspace = f"{container_case_root}/{project}"

        if host_case_root.exists():
            shutil.rmtree(host_case_root, ignore_errors=True)
        host_case_root.mkdir(parents=True, exist_ok=True)

        try:
            logger.info("Checking out '%s' (project=%s, bug_id=%s)...", bug.id, project, bug_id)
            self._checkout(dataset, bug, context, container_case_root, project, bug_id, version)
            self._validate_checkout(host_project_workspace, bug.id)
            logger.info("Compiling '%s' (may take several minutes on first run)...", bug.id)
            self._compile(dataset, bug, context, container_project_workspace)
            self._validate_compile(host_project_workspace, bug.id, dataset.tooling.get("compile_required", True))
        except Exception:
            shutil.rmtree(host_case_root, ignore_errors=True)
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
            host_workspace=host_project_workspace,
            container_workspace=container_project_workspace,
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
        container_case_root: str,
        project: str,
        bug_id: str,
        version: str,
    ) -> None:
        checkout_template = dataset.tooling.get("checkout_command_template")
        if not checkout_template:
            raise ValueError(f"BugsInPy adapter requires dataset.tooling.checkout_command_template for bug '{bug.id}'")
        command = checkout_template.format(
            project=project,
            bug_id=bug_id,
            version=version,
            host_workspace=str(context.host_workspace_root / bug.id),
            container_workspace=container_case_root,
        )
        result = self._run_in_bugsinpy_container(context, command, cwd=container_case_root, timeout_seconds=120)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(f"Checkout failed for '{bug.id}': {stderr}")

    def _validate_checkout(self, host_project_workspace: Path, bug_id: str) -> None:
        missing = []
        for name in self._CHECKOUT_REQUIRED_FILES:
            if not (host_project_workspace / name).exists():
                missing.append(name)
        if missing:
            raise RuntimeError(
                f"Checkout validation failed for '{bug_id}': missing {', '.join(missing)} in {host_project_workspace}"
            )

    def _compile(
        self,
        dataset: DatasetConfig,
        bug: BugEntry,
        context: DatasetPreparationContext,
        container_project_workspace: str,
    ) -> None:
        compile_command = dataset.tooling.get("compile_command")
        if not compile_command:
            return
        result = self._run_in_bugsinpy_container(context, compile_command, cwd=container_project_workspace, timeout_seconds=900)
        if result.returncode != 0:
            compile_required = dataset.tooling.get("compile_required", True)
            stderr = (result.stderr or "").strip()
            msg = f"Compile command failed for '{bug.id}': {stderr}"
            if compile_required:
                raise RuntimeError(msg)
            logger.warning(msg)

    def _validate_compile(
        self,
        host_project_workspace: Path,
        bug_id: str,
        compile_required: bool,
    ) -> None:
        if not compile_required:
            return
        missing = []
        for name in self._COMPILE_REQUIRED_FILES:
            if not (host_project_workspace / name).exists():
                missing.append(name)
        if missing:
            raise RuntimeError(
                f"Compile validation failed for '{bug_id}': missing {', '.join(missing)} in {host_project_workspace}"
            )

    def _run_in_bugsinpy_container(
        self,
        context: DatasetPreparationContext,
        command: str,
        cwd: str | None = None,
        timeout_seconds: int = 300,
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
            wrapped = f"cd {shlex.quote(cwd)} && {command}"
        else:
            wrapped = command
        cmd.append(wrapped)
        try:
            return subprocess.run(
                cmd,
                cwd=str(context.project_dir),
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Container preparation timed out after {timeout_seconds}s running: {command[:200]}")

    def _resolve_test_command(self, dataset: DatasetConfig, bug: BugEntry) -> str:
        if bug.test_command is not None:
            return bug.test_command
        # Use the venv created by bugsinpy-compile. Both this command and the
        # venv run in bugsinpy-runner (Python 3.8), so the symlinks in env/
        # always resolve to the correct interpreter.
        # pip install -e . --no-deps registers the project package in the venv without
        # disturbing pinned requirements. Required for projects like httpie whose
        # bugsinpy_requirements.txt omits the package itself.  Also corrects thefuck,
        # where the editable install points at env/src/<project> (a separate git clone)
        # instead of the workspace root, causing agent edits to be invisible at test time.
        return (
            "test -x env/bin/python && test -f bugsinpy_run_test.sh && test -f bugsinpy_compile_flag || exit 2; "
            "env/bin/pip install -e . --no-deps -q 2>/dev/null || true; "
            # Some compiled venvs (e.g. luigi-1) are missing env/bin/pytest — env/bin/python
            # is present but pytest was not pinned by bugsinpy-compile.  Ensure it is available
            # before running the test script so bash bugsinpy_run_test.sh resolves the correct
            # env/bin/pytest rather than falling back to the system uv-managed Python 3.14.
            "(env/bin/python -m pytest --version >/dev/null 2>&1 || env/bin/pip install pytest -q 2>/dev/null || true); "
            'PATH="$(pwd)/env/bin:$PATH" VIRTUAL_ENV="$(pwd)/env" bash bugsinpy_run_test.sh'
        )


def is_bugsinpy_metadata(metadata: dict[str, object]) -> bool:
    return metadata.get("dataset_type") == "bugsinpy"


def compile_required_from_metadata(metadata: dict[str, object]) -> bool:
    raw = metadata.get("bugsinpy_compile_required")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if normalized in {"1", "true", "yes", "y"}:
            return True
        if normalized in {"0", "false", "no", "n"}:
            return False
    return True


def missing_workspace_artifacts(repo_root: Path, *, compile_required: bool) -> list[str]:
    required = list(BugsInPyAdapter._CHECKOUT_REQUIRED_FILES)
    if compile_required:
        required.extend(BugsInPyAdapter._COMPILE_REQUIRED_FILES)
    missing: list[str] = []
    for name in required:
        if not (repo_root / name).exists():
            missing.append(name)
    return missing
