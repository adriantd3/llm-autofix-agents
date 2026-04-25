from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from llm_autofix_agents.tools.context import APRToolContext


def workspace_root(ctx: APRToolContext) -> Path:
    root = Path(ctx.root_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_path(ctx: APRToolContext, rel_path: str) -> Path:
    root = workspace_root(ctx)
    candidate = (root / rel_path).expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path escapes workspace root: {rel_path}") from exc
    return candidate


def safe_rel(root: Path, path: Path) -> str:
    return str(path.relative_to(root))


def iter_files(root: Path, pattern: str) -> Iterable[Path]:
    for path in root.glob(pattern):
        if path.is_file():
            yield path
