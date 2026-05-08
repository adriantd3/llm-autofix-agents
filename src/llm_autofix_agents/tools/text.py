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


def compact_test_output(text: str, max_chars: int = 4000) -> str:
    if max_chars <= 0:
        return ""
    if not text:
        return text

    lines = text.splitlines()
    lines = _collapse_repeated_blocks(lines)
    lines = _collapse_repeated_lines(lines)
    compacted = "\n".join(lines)
    if len(compacted) <= max_chars:
        return compacted

    return _truncate_middle(compacted, max_chars=max_chars)


def _collapse_repeated_blocks(lines: list[str], *, max_repeats: int = 3, max_block_len: int = 50) -> list[str]:
    if len(lines) < 4:
        return lines

    result: list[str] = []
    index = 0
    total = len(lines)

    while index < total:
        block_len, repeats = _find_repeated_block(lines, index, max_block_len)
        if repeats > 1:
            keep = min(max_repeats, repeats)
            for _ in range(keep):
                result.extend(lines[index : index + block_len])
            omitted = repeats - keep
            if omitted:
                result.append(f"[collapsed {omitted} repeated blocks]")
            index += block_len * repeats
            continue
        result.append(lines[index])
        index += 1

    return result


def _find_repeated_block(lines: list[str], start: int, max_block_len: int) -> tuple[int, int]:
    remaining = len(lines) - start
    max_len = min(max_block_len, remaining // 2)
    for block_len in range(2, max_len + 1):
        block = lines[start : start + block_len]
        next_block = lines[start + block_len : start + 2 * block_len]
        if block != next_block:
            continue
        repeats = 2
        while start + repeats * block_len <= len(lines):
            candidate = lines[start + (repeats - 1) * block_len : start + repeats * block_len]
            if candidate != block:
                break
            repeats += 1
        return block_len, repeats - 1
    return 0, 1


def _collapse_repeated_lines(lines: list[str], *, max_repeats: int = 3) -> list[str]:
    if not lines:
        return lines

    result: list[str] = []
    current = lines[0]
    count = 1

    for line in lines[1:]:
        if line == current:
            count += 1
            continue
        result.extend([current] * min(count, max_repeats))
        omitted = count - max_repeats
        if omitted > 0:
            result.append(f"[collapsed {omitted} repeated lines]")
        current = line
        count = 1

    result.extend([current] * min(count, max_repeats))
    omitted = count - max_repeats
    if omitted > 0:
        result.append(f"[collapsed {omitted} repeated lines]")

    return result


def _truncate_middle(text: str, *, max_chars: int) -> str:
    marker_template = "[truncated {count} chars]"
    marker = marker_template.format(count=len(text))
    overhead = len(marker) + 2
    if max_chars <= overhead:
        return text[-max_chars:]

    head_len = max(1, (max_chars - overhead) // 2)
    tail_len = max_chars - overhead - head_len
    if tail_len < 1:
        tail_len = 1
        head_len = max(1, max_chars - overhead - tail_len)

    for _ in range(3):
        omitted = len(text) - head_len - tail_len
        marker = marker_template.format(count=omitted)
        overhead = len(marker) + 2
        available = max_chars - overhead
        if available < 2:
            return text[-max_chars:]
        head_len = max(1, available // 2)
        tail_len = max(1, available - head_len)

    return f"{text[:head_len]}\n{marker}\n{text[-tail_len:]}"


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
    if (root / "bugsinpy_run_test.sh").exists():
        return "bugsinpy", "bugsinpy-test"
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
