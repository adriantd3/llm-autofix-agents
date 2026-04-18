from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


def resolve_repo_root(target_repo: str | None) -> Path:
    repo_root = Path(target_repo if target_repo else ".").resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        raise ValueError(f"Invalid target repository: {repo_root}")
    return repo_root


def snapshot_repo_state(repo_root: Path) -> dict[str, str]:
    ignored_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", "results"}
    snapshot: dict[str, str] = {}
    for file_path in repo_root.rglob("*"):
        if not file_path.is_file():
            continue
        if any(part in ignored_dirs for part in file_path.parts):
            continue
        relative = file_path.relative_to(repo_root).as_posix()
        try:
            digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
        except OSError:
            continue
        snapshot[relative] = digest
    return snapshot


def detect_changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    changed: set[str] = set()
    for path, digest in before.items():
        if path not in after or after[path] != digest:
            changed.add(path)
    for path in after:
        if path not in before:
            changed.add(path)
    return sorted(changed)


def collect_repo_diff(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "diff", "--no-color"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()
