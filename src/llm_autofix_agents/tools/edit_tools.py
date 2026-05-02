from __future__ import annotations

from agents import RunContextWrapper, function_tool

from llm_autofix_agents.tools.context import APRToolContext, get_tool_context
from llm_autofix_agents.tools.paths import resolve_path
from llm_autofix_agents.tools.serialization import json_result
from llm_autofix_agents.tools.text import read_text_checked


_TEST_FILE_REJECTION = (
    "Modifying test files is FORBIDDEN. The failing tests are CORRECT. "
    "Fix ONLY source code files (implementation, not tests)."
)


def _is_test_file_path(path: str) -> bool:
    lowered = path.lower().replace("\\", "/")
    if lowered.startswith("test/") or lowered.startswith("tests/"):
        return True
    parts = lowered.split("/")
    for part in parts:
        stem = part.rsplit(".", 1)[0] if "." in part else part
        if stem.startswith("test_") or stem.endswith("_test"):
            return True
    return False


def _reject_if_test_file(path: str) -> str | None:
    if _is_test_file_path(path):
        return json_result(
            {
                "ok": False,
                "error": "test_file_modification_forbidden",
                "path": path,
                "message": _TEST_FILE_REJECTION,
            }
        )
    return None


@function_tool
def write_file(
    ctx: RunContextWrapper[APRToolContext],
    path: str,
    content: str,
    create_dirs: bool = True,
    overwrite: bool = True,
) -> str:
    """Write a complete text file inside the workspace."""
    rejection = _reject_if_test_file(path)
    if rejection is not None:
        return rejection
    cfg = get_tool_context(ctx)
    file_path = resolve_path(cfg, path)
    if file_path.exists() and file_path.is_dir():
        return json_result({"ok": False, "error": "path_is_directory", "path": path})
    if file_path.exists() and not overwrite:
        return json_result({"ok": False, "error": "file_exists", "path": path})
    if create_dirs:
        file_path.parent.mkdir(parents=True, exist_ok=True)
    elif not file_path.parent.exists():
        return json_result({"ok": False, "error": "parent_missing", "path": path})
    file_path.write_text(content, encoding="utf-8")
    return json_result({"ok": True, "path": path, "bytes_written": len(content.encode("utf-8"))})


@function_tool
def replace_in_file(
    ctx: RunContextWrapper[APRToolContext],
    path: str,
    old: str,
    new: str,
    replace_all: bool = False,
    expected_occurrences: int | None = None,
) -> str:
    """Perform an exact text replacement in a file."""
    rejection = _reject_if_test_file(path)
    if rejection is not None:
        return rejection
    cfg = get_tool_context(ctx)
    file_path = resolve_path(cfg, path)
    ok, error, original = read_text_checked(cfg, file_path)
    if not ok:
        return json_result({"ok": False, "error": error, "path": path})

    source = original or ""
    occurrences = source.count(old)
    if expected_occurrences is not None and occurrences != expected_occurrences:
        return json_result(
            {
                "ok": False,
                "error": "unexpected_occurrence_count",
                "path": path,
                "expected_occurrences": expected_occurrences,
                "actual_occurrences": occurrences,
            }
        )
    if occurrences == 0:
        return json_result({"ok": False, "error": "old_text_not_found", "path": path})

    updated = source.replace(old, new) if replace_all else source.replace(old, new, 1)
    file_path.write_text(updated, encoding="utf-8")
    return json_result(
        {
            "ok": True,
            "path": path,
            "replaced": occurrences if replace_all else 1,
            "bytes_written": len(updated.encode("utf-8")),
        }
    )


@function_tool
def replace_lines(
    ctx: RunContextWrapper[APRToolContext],
    path: str,
    start_line: int,
    end_line: int,
    new_lines: str,
) -> str:
    """Replace an inclusive line range in a text file."""
    rejection = _reject_if_test_file(path)
    if rejection is not None:
        return rejection
    cfg = get_tool_context(ctx)
    file_path = resolve_path(cfg, path)
    ok, error, original = read_text_checked(cfg, file_path)
    if not ok:
        return json_result({"ok": False, "error": error, "path": path})

    lines = (original or "").splitlines(keepends=True)
    if not lines and start_line == 1 and end_line == 1:
        lines = []
    if start_line < 1 or end_line < start_line or end_line > max(len(lines), 1):
        return json_result(
            {
                "ok": False,
                "error": "invalid_line_range",
                "path": path,
                "start_line": start_line,
                "end_line": end_line,
                "line_count": len(lines),
            }
        )

    replacement = new_lines.splitlines(keepends=True)
    if new_lines and not new_lines.endswith(("\n", "\r")):
        replacement = new_lines.splitlines(keepends=False)
        replacement = [line + "\n" for line in replacement[:-1]] + ([replacement[-1]] if replacement else [])
    updated_lines = lines[: start_line - 1] + replacement + lines[end_line:]
    updated = "".join(updated_lines)
    file_path.write_text(updated, encoding="utf-8")
    return json_result({"ok": True, "path": path, "start_line": start_line, "end_line": end_line})
