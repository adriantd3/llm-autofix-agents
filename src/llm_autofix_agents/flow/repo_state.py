from __future__ import annotations

import fnmatch
import hashlib
import subprocess
from pathlib import Path

_DEFAULT_IGNORE_PATTERNS = [
    ".git/",
    ".venv/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    "results/",
    "build/",
    "dist/",
    "*.egg-info/",
    "htmlcov/",
    ".coverage",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.o",
]


def resolve_repo_root(target_repo: str | None) -> Path:
    repo_root = Path(target_repo if target_repo else ".").resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        raise ValueError(f"Invalid target repository: {repo_root}")
    return repo_root


def snapshot_repo_state(repo_root: Path) -> dict[str, str]:
    ignore_rules = load_ignore_rules(repo_root)
    snapshot: dict[str, str] = {}
    for file_path in repo_root.rglob("*"):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(repo_root).as_posix()
        if should_ignore_path(relative, ignore_rules):
            continue
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
    ignore_rules = load_ignore_rules(repo_root)
    return filter_diff_by_ignore_rules(result.stdout.strip(), ignore_rules).strip()


def load_ignore_rules(repo_root: Path) -> list[str]:
    ignore_file = repo_root / ".autofixignore"
    rules = list(_DEFAULT_IGNORE_PATTERNS)
    if not ignore_file.exists():
        return rules
    try:
        for raw_line in ignore_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            rules.append(line)
    except OSError:
        return rules
    return rules


def should_ignore_path(path: str, ignore_rules: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    directory_path = f"{normalized}/"
    for rule in ignore_rules:
        cleaned_rule = rule.strip().replace("\\", "/")
        if not cleaned_rule:
            continue
        if cleaned_rule.endswith("/"):
            prefix = cleaned_rule.removeprefix("./")
            if directory_path.startswith(prefix):
                return True
            if f"/{prefix}" in directory_path:
                return True
            continue
        if "/" in cleaned_rule:
            if fnmatch.fnmatch(normalized, cleaned_rule):
                return True
            continue
        if fnmatch.fnmatch(Path(normalized).name, cleaned_rule):
            return True
    return False


def filter_diff_by_ignore_rules(diff: str, ignore_rules: list[str]) -> str:
    if not diff.strip():
        return ""

    chunks: list[list[str]] = []
    current_chunk: list[str] = []
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = [line]
            continue
        if not current_chunk:
            continue
        current_chunk.append(line)
    if current_chunk:
        chunks.append(current_chunk)

    filtered_chunks: list[str] = []
    for chunk in chunks:
        header = chunk[0]
        parts = header.split(" ")
        if len(parts) < 4:
            filtered_chunks.append("\n".join(chunk))
            continue
        a_path = parts[2].removeprefix("a/")
        b_path = parts[3].removeprefix("b/")
        if should_ignore_path(a_path, ignore_rules) and should_ignore_path(b_path, ignore_rules):
            continue
        filtered_chunks.append("\n".join(chunk))

    return "\n\n".join(filtered_chunks)
