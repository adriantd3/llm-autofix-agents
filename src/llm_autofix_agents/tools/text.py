from __future__ import annotations

import mimetypes
from pathlib import Path

from llm_autofix_agents.tools.context import APRToolContext


def is_probably_text(path: Path) -> bool:
    mime, _ = mimetypes.guess_type(path.name)
    if mime and (mime.startswith("text/") or mime in {"application/json", "application/xml", "application/x-yaml"}):
        return True
    try:
        with path.open("rb") as file:
            chunk = file.read(4096)
        if b"\x00" in chunk:
            return False
        chunk.decode("utf-8")
        return True
    except Exception:
        return False


def truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def slice_lines(lines: list[str], start_line: int | None, end_line: int | None) -> tuple[list[str], int, int]:
    start = 1 if start_line is None else max(1, start_line)
    end = len(lines) if end_line is None else min(len(lines), max(start, end_line))
    return lines[start - 1 : end], start, end


def read_text_checked(cfg: APRToolContext, path: Path) -> tuple[bool, str | None, str | None]:
    if not path.exists():
        return False, "file_not_found", None
    if not path.is_file():
        return False, "not_a_file", None
    if path.stat().st_size > cfg.max_file_bytes:
        return False, "file_too_large", None
    if not is_probably_text(path):
        return False, "binary_or_non_text", None
    return True, None, path.read_text(encoding="utf-8", errors="replace")


def detect_test_command(root: Path) -> tuple[str, str] | None:
    if (root / "pytest.ini").exists() or (root / "conftest.py").exists() or list(root.glob("tests/test_*.py")):
        return "pytest", "pytest -q"
    if (root / "pyproject.toml").exists():
        text = (root / "pyproject.toml").read_text(encoding="utf-8", errors="replace")
        if "[tool.pytest.ini_options]" in text or "pytest" in text:
            return "pytest", "pytest -q"
    if (root / "manage.py").exists():
        return "django", "python manage.py test"
    if (root / "package.json").exists():
        return "npm", "npm test -- --runInBand"
    if (root / "Cargo.toml").exists():
        return "cargo", "cargo test --quiet"
    return None
