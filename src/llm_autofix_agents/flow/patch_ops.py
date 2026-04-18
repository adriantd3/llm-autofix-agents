from __future__ import annotations

import subprocess
from pathlib import Path

from llm_autofix_agents.flow.models import PatchApplyResult


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
