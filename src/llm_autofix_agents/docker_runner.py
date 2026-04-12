from __future__ import annotations

import shlex
import subprocess
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_RUNNER_IMAGE = "llm-autofix-runner:py313"
DEFAULT_WORKDIR = "/workspace"

_SMALL_PROJECT_SIZE_BYTES = 50 * 1024 * 1024
_MEDIUM_PROJECT_SIZE_BYTES = 250 * 1024 * 1024
_IGNORED_SIZE_PARTS = {
    ".git",
    ".venv",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
}


class DockerRunnerError(RuntimeError):
    """Raised when the Docker runner cannot execute a request."""


@dataclass(frozen=True)
class ResourceLimits:
    cpus: float
    memory: str
    pids_limit: int
    timeout_seconds: int

    def __post_init__(self) -> None:
        if self.cpus <= 0:
            raise ValueError("cpus must be greater than zero")
        if self.pids_limit <= 0:
            raise ValueError("pids_limit must be greater than zero")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if not self.memory.strip():
            raise ValueError("memory cannot be empty")


@dataclass(frozen=True)
class ContainerRunRequest:
    repo_path: Path
    command: str
    image: str = DEFAULT_RUNNER_IMAGE
    limits: ResourceLimits | None = None

    def __post_init__(self) -> None:
        if not self.command.strip():
            raise ValueError("command cannot be empty")
        if not self.image.strip():
            raise ValueError("image cannot be empty")


@dataclass(frozen=True)
class ContainerRunResult:
    command: str
    image: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_seconds: float
    started_at_utc: str
    finished_at_utc: str
    container_name: str
    audit_events: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "command": self.command,
            "image": self.image,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "duration_seconds": self.duration_seconds,
            "started_at_utc": self.started_at_utc,
            "finished_at_utc": self.finished_at_utc,
            "container_name": self.container_name,
            "audit_events": list(self.audit_events),
        }


def resolve_dynamic_limits(repo_path: Path) -> ResourceLimits:
    """Provide baseline dynamic limits based on project size on disk."""
    total_size = _estimate_repo_size(repo_path)
    if total_size <= _SMALL_PROJECT_SIZE_BYTES:
        return ResourceLimits(cpus=1.0, memory="1g", pids_limit=256, timeout_seconds=120)
    if total_size <= _MEDIUM_PROJECT_SIZE_BYTES:
        return ResourceLimits(cpus=2.0, memory="2g", pids_limit=512, timeout_seconds=300)
    return ResourceLimits(cpus=3.0, memory="4g", pids_limit=1024, timeout_seconds=600)


class DockerRunner:
    def __init__(self, docker_executable: str = "docker", network_mode: str = "bridge") -> None:
        self._docker_executable = docker_executable
        self._network_mode = network_mode

    def assert_docker_available(self) -> None:
        command = [self._docker_executable, "version", "--format", "{{.Server.Version}}"]
        completed = subprocess.run(command, capture_output=True, check=False, text=True)
        if completed.returncode != 0:
            raise DockerRunnerError(
                "Docker no esta disponible. Ejecuta Docker Desktop y vuelve a intentarlo. "
                f"Detalle: {completed.stderr.strip()}"
            )

    def run(self, request: ContainerRunRequest) -> ContainerRunResult:
        self.assert_docker_available()

        repo_path = request.repo_path.resolve()
        if not repo_path.is_dir():
            raise DockerRunnerError(f"Ruta de repositorio invalida para bind mount: {repo_path}")

        limits = request.limits if request.limits is not None else resolve_dynamic_limits(repo_path)
        container_name = f"autofix-run-{uuid.uuid4().hex[:12]}"

        docker_command = self._build_docker_command(
            container_name=container_name,
            repo_path=repo_path,
            command=request.command,
            image=request.image,
            limits=limits,
        )

        started_at = datetime.now(UTC)
        audit_events = [
            f"docker_command={_shell_join(docker_command)}",
            f"repo_mount={repo_path}",
            f"network_mode={self._network_mode}",
        ]

        try:
            completed = subprocess.run(
                docker_command,
                capture_output=True,
                check=False,
                text=True,
                timeout=limits.timeout_seconds,
            )
            finished_at = datetime.now(UTC)
            audit_events.append(f"exit_code={completed.returncode}")
            return ContainerRunResult(
                command=request.command,
                image=request.image,
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                timed_out=False,
                duration_seconds=(finished_at - started_at).total_seconds(),
                started_at_utc=_iso_timestamp(started_at),
                finished_at_utc=_iso_timestamp(finished_at),
                container_name=container_name,
                audit_events=tuple(audit_events),
            )
        except subprocess.TimeoutExpired as exc:
            self._force_remove_container(container_name)
            finished_at = datetime.now(UTC)
            audit_events.append("timeout=true")
            return ContainerRunResult(
                command=request.command,
                image=request.image,
                exit_code=124,
                stdout=_coerce_stream(exc.stdout),
                stderr=_coerce_stream(exc.stderr),
                timed_out=True,
                duration_seconds=(finished_at - started_at).total_seconds(),
                started_at_utc=_iso_timestamp(started_at),
                finished_at_utc=_iso_timestamp(finished_at),
                container_name=container_name,
                audit_events=tuple(audit_events),
            )

    def _build_docker_command(
        self,
        *,
        container_name: str,
        repo_path: Path,
        command: str,
        image: str,
        limits: ResourceLimits,
    ) -> list[str]:
        mount_spec = f"type=bind,src={repo_path},dst={DEFAULT_WORKDIR}"
        return [
            self._docker_executable,
            "run",
            "--rm",
            "--init",
            "--name",
            container_name,
            "--workdir",
            DEFAULT_WORKDIR,
            "--mount",
            mount_spec,
            "--security-opt",
            "no-new-privileges:true",
            "--cap-drop",
            "ALL",
            "--cpus",
            f"{limits.cpus:.2f}",
            "--memory",
            limits.memory,
            "--pids-limit",
            str(limits.pids_limit),
            "--network",
            self._network_mode,
            image,
            "sh",
            "-lc",
            command,
        ]

    def _force_remove_container(self, container_name: str) -> None:
        subprocess.run(
            [self._docker_executable, "rm", "-f", container_name],
            capture_output=True,
            check=False,
            text=True,
        )


def _estimate_repo_size(repo_path: Path) -> int:
    size = 0
    for path in repo_path.rglob("*"):
        if any(part in _IGNORED_SIZE_PARTS for part in path.parts):
            continue
        if not path.is_file():
            continue
        try:
            size += path.stat().st_size
        except OSError:
            continue
    return size


def _iso_timestamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _coerce_stream(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _shell_join(parts: list[str]) -> str:
    return shlex.join(parts)
