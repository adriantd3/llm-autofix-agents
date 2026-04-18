from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from llm_autofix_agents.contracts import RunInput, TestResults


@dataclass(frozen=True)
class TestExecution:
    exit_code: int
    timed_out: bool
    output: str
    signature: str


@dataclass(frozen=True)
class PatchApplyResult:
    applied: bool
    reason: str


def resolve_test_timeout_seconds(metadata: dict[str, object]) -> int:
    value = metadata.get("test_timeout_seconds")
    if value is None:
        return 120
    if not isinstance(value, int):
        raise ValueError("metadata.test_timeout_seconds must be an integer")
    if value < 1 or value > 1800:
        raise ValueError("metadata.test_timeout_seconds must be between 1 and 1800")
    return value


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


def run_test_command(test_command: str | None, *, cwd: Path, timeout_seconds: int) -> TestExecution:
    if test_command is None:
        return TestExecution(exit_code=0, timed_out=False, output="", signature="no-tests")

    try:
        completed = subprocess.run(
            test_command,
            cwd=str(cwd),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        output = f"{completed.stdout}\n{completed.stderr}".strip()
        signature = build_test_signature(exit_code=completed.returncode, timed_out=False, output=output)
        return TestExecution(
            exit_code=completed.returncode,
            timed_out=False,
            output=output,
            signature=signature,
        )
    except subprocess.TimeoutExpired as exc:
        output = f"timeout: {exc}"
        signature = build_test_signature(exit_code=124, timed_out=True, output=output)
        return TestExecution(exit_code=124, timed_out=True, output=output, signature=signature)


def build_test_signature(*, exit_code: int, timed_out: bool, output: str) -> str:
    normalized_output = " ".join(output.split()).strip().lower()
    payload = f"exit={exit_code}|timed_out={timed_out}|{normalized_output}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def to_test_results(test_execution: TestExecution) -> TestResults:
    output = test_execution.output
    total = extract_int(output, r"Ran\s+(\d+)\s+tests?")

    passed = sum_counts(output, [r"(\d+)\s+passed"])
    failed = sum_counts(
        output,
        [
            r"(\d+)\s+failed",
            r"failures?=(\d+)",
            r"errors?=(\d+)",
        ],
    )

    if test_execution.exit_code == 0 and failed == 0:
        if total == 0:
            total = passed
        return TestResults(total=total, passed=passed, failed=0)

    if failed == 0:
        failed = 1

    if total < passed + failed:
        total = passed + failed

    return TestResults(total=total, passed=passed, failed=failed)


def extract_int(text: str, pattern: str) -> int:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if match is None:
        return 0
    return int(match.group(1))


def sum_counts(text: str, patterns: list[str]) -> int:
    total = 0
    for pattern in patterns:
        for value in re.findall(pattern, text, flags=re.IGNORECASE):
            total += int(value)
    return total


def build_iteration_input(
    *,
    prompt: str,
    iteration: int,
    max_iterations: int,
    previous_message: str | None,
) -> str:
    if previous_message is None:
        return prompt
    return (
        f"[ITERATION {iteration}/{max_iterations}]\n"
        f"Previous attempt summary:\n{previous_message}\n\n"
        "Continue improving the repair strategy and validate with available tools.\n"
        f"Original prompt:\n{prompt}"
    )


def is_no_progress(
    *,
    previous_message: str | None,
    current_message: str,
    previous_test_signature: str | None,
    current_test_signature: str,
    changed_files: list[str],
) -> bool:
    if previous_message is None or previous_test_signature is None:
        return False

    previous_normalized = " ".join(previous_message.split()).strip().lower()
    current_normalized = " ".join(current_message.split()).strip().lower()
    same_message = previous_normalized == current_normalized
    same_test_signature = previous_test_signature == current_test_signature
    no_file_changes = len(changed_files) == 0
    return same_message and same_test_signature and no_file_changes


def can_complete_early(*, run_input: RunInput, test_execution: TestExecution) -> bool:
    if run_input.test_command is None:
        return True
    return test_execution.exit_code == 0 and not test_execution.timed_out


def is_regression(*, baseline: TestExecution, current: TestExecution) -> bool:
    return baseline.exit_code == 0 and current.exit_code != 0


def apply_unified_diff(*, repo_root: Path, patch: str) -> PatchApplyResult:
    if not patch:
        return PatchApplyResult(applied=False, reason="no-patch")

    check = run_git_apply(repo_root=repo_root, patch=patch, args=["--check"])
    if check.returncode != 0:
        stderr = (check.stderr or "").strip()
        return PatchApplyResult(applied=False, reason=stderr or "patch-check-failed")

    apply = run_git_apply(repo_root=repo_root, patch=patch, args=[])
    if apply.returncode != 0:
        stderr = (apply.stderr or "").strip()
        return PatchApplyResult(applied=False, reason=stderr or "patch-apply-failed")

    return PatchApplyResult(applied=True, reason="applied")


def run_git_apply(*, repo_root: Path, patch: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "apply", "--whitespace=nowarn", *args, "-"],
        cwd=str(repo_root),
        input=patch,
        capture_output=True,
        text=True,
        check=False,
    )


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
