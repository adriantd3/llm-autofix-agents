from __future__ import annotations

from pathlib import Path

# Paths relative to the canonical root for each dataset type.
# QuixBugs: the root is the cloned QuixBugs repository.
#   Ground truth = correct_python_programs/{bug_id}.py
# BugsInPy: the root is the cloned BugsInPy repository.
#   Ground truth = projects/{project}/bugs/{number}/bug_patch.txt
#   problem_id format: "{project}-{number}" (e.g. "httpie-1", "youtube-dl-3")
_QUIXBUGS_TEMPLATE = "correct_python_programs/{bug_id}.py"
_BUGSINPY_TEMPLATE = "projects/{project}/bugs/{number}/bug_patch.txt"


def _parse_bugsinpy_problem_id(problem_id: str) -> tuple[str, str]:
    """Split a BugsInPy problem_id into (project, bug_number).

    The problem_id is formatted as "{project}-{number}" where project may
    itself contain hyphens (e.g. "youtube-dl-1" → ("youtube-dl", "1")).
    """
    parts = problem_id.rsplit("-", maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        return problem_id, ""
    return parts[0], parts[1]


def resolve_canonical_patch(
    *,
    dataset_type: str,
    problem_id: str,
    canonical_root: Path | None,
) -> str | None:
    """Return the ground-truth content for a bug, or None if unavailable.

    Args:
        dataset_type: "quixbugs" or "bugsinpy".
        problem_id: The bug identifier (e.g. "gcd" for QuixBugs, "youtube-dl-1"
            for BugsInPy).
        canonical_root: Base directory containing ground-truth patches.
            Pass None to skip canonical comparison entirely.
    """
    if canonical_root is None:
        return None

    if dataset_type == "quixbugs":
        path = canonical_root / _QUIXBUGS_TEMPLATE.format(bug_id=problem_id)
    elif dataset_type == "bugsinpy":
        project, number = _parse_bugsinpy_problem_id(problem_id)
        if not number:
            return None
        path = canonical_root / _BUGSINPY_TEMPLATE.format(project=project, number=number)
    else:
        return None

    if not path.exists():
        return None

    return path.read_text(encoding="utf-8")
