from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import mkdtemp

_GITHUB_SLUG_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


@dataclass(slots=True)
class PreparedRepository:
    path: Path
    temporary: bool

    def cleanup(self) -> None:
        if not self.temporary:
            return
        shutil.rmtree(self.path, ignore_errors=True)


def prepare_target_repository(*, repository: str, branch: str | None = None) -> PreparedRepository:
    normalized_repository = repository.strip()
    if not normalized_repository:
        raise ValueError("RUN_REPOSITORY cannot be empty")

    local_path = Path(normalized_repository)
    if local_path.is_dir():
        return PreparedRepository(path=local_path.resolve(), temporary=False)

    if not branch:
        raise ValueError("branch is required when repository is a remote URL or GitHub slug")

    clone_url = _to_clone_url(normalized_repository)
    destination = Path(mkdtemp(prefix="autofix-repo-"))
    command = [
        "git",
        "clone",
        "--depth",
        "1",
        "--branch",
        branch.strip(),
        clone_url,
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        shutil.rmtree(destination, ignore_errors=True)
        stderr = (result.stderr or "").strip()
        raise ValueError(f"Failed to clone repository '{normalized_repository}': {stderr}")

    return PreparedRepository(path=destination.resolve(), temporary=True)


def _to_clone_url(repository: str) -> str:
    if repository.startswith(("http://", "https://", "git@")):
        return repository
    if _GITHUB_SLUG_PATTERN.match(repository):
        return f"https://github.com/{repository}.git"
    raise ValueError("RUN_REPOSITORY must be a git URL or a GitHub slug like owner/repo")
