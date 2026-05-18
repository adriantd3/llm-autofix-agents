from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents import RunContextWrapper, function_tool

from llm_autofix_agents.tools.context import APRToolContext, get_tool_context
from llm_autofix_agents.tools.metadata import (
    ToolDescriptor,
    ToolResultKind,
    classify_json_envelope,
    content_hash,
    make_json_result_summarizer,
)
from llm_autofix_agents.tools.paths import resolve_path
from llm_autofix_agents.tools.registry import register
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
        if stem in ("test", "tests"):
            return True
        if stem.startswith("test_") or stem.startswith("tests_") or stem.endswith("_test"):
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
    """Write the complete content of a file inside the workspace.

    Use ONLY for creating new files or fully rewriting small files (under 50 lines).
    NEVER overwrite a large existing source file with partial content — the rest of the
    module will be destroyed. Use replace_in_file or replace_lines for targeted edits.
    Paths must be relative to the workspace root.
    """
    rejection = _reject_if_test_file(path)
    if rejection is not None:
        return rejection
    cfg = get_tool_context(ctx)
    file_path = resolve_path(cfg, path)
    if file_path.exists() and file_path.is_dir():
        return json_result({"ok": False, "error": "path_is_directory", "path": path})
    if file_path.exists() and not overwrite:
        return json_result({"ok": False, "error": "file_exists", "path": path})
    # Guard: LLMs sometimes write a partial rewrite/stub to a large source file, destroying the rest.
    # E2E trace (2026-05-13): agent wrote 600-line content to a 1163-line file (51% — not blocked
    # by the 1/3 threshold) and destroyed the module.  Raised to 2/3: any write that reduces a
    # large file by more than ~33% is treated as accidental truncation.
    if file_path.exists():
        existing_lines = file_path.read_text(encoding="utf-8").count("\n")
        new_lines = content.count("\n")
        if existing_lines > 50 and new_lines < existing_lines * 2 // 3:
            return json_result({
                "ok": False,
                "error": "write_file_would_truncate",
                "existing_lines": existing_lines,
                "new_lines": new_lines,
                "message": (
                    f"Cannot overwrite a {existing_lines}-line file with {new_lines} lines. "
                    "Use replace_in_file or replace_lines for targeted edits."
                ),
            })
    if create_dirs:
        file_path.parent.mkdir(parents=True, exist_ok=True)
    elif not file_path.parent.exists():
        return json_result({"ok": False, "error": "parent_missing", "path": path})
    file_path.write_text(content, encoding="utf-8")
    cfg.iteration_edit_count += 1
    return json_result({"ok": True, "path": path, "bytes_written": len(content.encode("utf-8"))})


def _fuzzy_find_and_replace(source: str, old: str, new: str) -> str | None:
    """Replace the first occurrence of `old` in `source` using progressive fuzzy matching.

    Called only when exact matching already failed (source.count(old) == 0).
    Returns the updated source string, or None if not found by any pass.

    Pass 2 — CRLF normalisation: LLM output always uses \\n; the target file may use \\r\\n.
    Pass 3 — trailing-whitespace strip: LLMs routinely omit trailing spaces on lines.
    """
    # Normalize line endings for passes 2 and 3 (non-destructive: we work in normalized space
    # and write the normalized form back, which is safe for Python source files).
    src_n = source.replace("\r\n", "\n").replace("\r", "\n")
    old_n = old.replace("\r\n", "\n").replace("\r", "\n")

    # Pass 2: CRLF-normalized match
    if old_n in src_n:
        return src_n.replace(old_n, new, 1)

    # Pass 3: strip trailing whitespace per line before comparing
    old_lines = old_n.splitlines()
    if not old_lines:
        return None
    old_stripped = [line.rstrip() for line in old_lines]
    src_lines = src_n.splitlines(keepends=True)
    n = len(old_lines)
    for i in range(len(src_lines) - n + 1):
        candidate = [src_lines[i + j].rstrip("\n").rstrip() for j in range(n)]
        if candidate == old_stripped:
            prefix = "".join(src_lines[:i])
            suffix = "".join(src_lines[i + n:])
            return prefix + new + suffix

    return None


@function_tool
def replace_in_file(
    ctx: RunContextWrapper[APRToolContext],
    path: str,
    old: str,
    new: str,
    replace_all: bool = False,
    expected_occurrences: int | None = None,
) -> str:
    """Replace an exact text block in a file.

    old must be copied verbatim from read_file output — it is the text to be replaced.
    Fuzzy matching handles minor whitespace/CRLF differences automatically.
    If old_text_not_found is returned: re-read the target section with read_file to get
    the current exact text, then retry. Never retry with the same old text — it will fail again.
    Paths must be relative to the workspace root.
    """
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
    fuzzy_matched = False

    if occurrences == 0 and not replace_all:
        # Exact match failed; attempt fuzzy matching before reporting not-found.
        # replace_all is excluded: fuzzy multi-match semantics are ambiguous.
        updated = _fuzzy_find_and_replace(source, old, new)
        if updated is None:
            return json_result({"ok": False, "error": "old_text_not_found", "path": path})
        fuzzy_matched = True
        occurrences = 1
    else:
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
    cfg.iteration_edit_count += 1
    result: dict[str, Any] = {
        "ok": True,
        "path": path,
        "replaced": occurrences if replace_all else 1,
        "bytes_written": len(updated.encode("utf-8")),
    }
    if fuzzy_matched:
        result["fuzzy_matched"] = True
    return json_result(result)


@function_tool
def replace_lines(
    ctx: RunContextWrapper[APRToolContext],
    path: str,
    start_line: int,
    end_line: int,
    new_lines: str,
) -> str:
    """Replace an inclusive line range in a file with new content.

    Use to insert new code (functions, imports) at a known line position.
    Get line numbers from read_file output. Paths must be relative to the workspace root.
    """
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
    cfg.iteration_edit_count += 1
    return json_result({"ok": True, "path": path, "start_line": start_line, "end_line": end_line})


# ---------------------------------------------------------------------------
# Observability metadata (SH1)
# ---------------------------------------------------------------------------


def _args_write_file(args: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": args.get("path"),
        "content_length": len(args.get("content", "")),
        "create_dirs": args.get("create_dirs", True),
        "overwrite": args.get("overwrite", True),
    }


def _args_replace_in_file(args: Mapping[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": args.get("path"),
        "replace_all": args.get("replace_all", False),
        "expected_occurrences": args.get("expected_occurrences"),
    }
    old = args.get("old", "")
    if old:
        summary["old_hash"] = content_hash(old)
        summary["old_length"] = len(old)
    new = args.get("new", "")
    if new:
        summary["new_hash"] = content_hash(new)
        summary["new_length"] = len(new)
    return summary


def _args_replace_lines(args: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": args.get("path"),
        "start_line": args.get("start_line"),
        "end_line": args.get("end_line"),
        "new_lines_length": len(args.get("new_lines", "")),
    }


def _result_write_file(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {"ok": ok, "path": payload.get("path")}
    if ok is True:
        summary["bytes_written"] = payload.get("bytes_written")
    else:
        summary["error"] = payload.get("error")
    return summary


def _result_replace_in_file(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {"ok": ok, "path": payload.get("path")}
    if ok is True:
        summary["replaced"] = payload.get("replaced")
        summary["bytes_written"] = payload.get("bytes_written")
        if payload.get("fuzzy_matched"):
            summary["fuzzy_matched"] = True
    else:
        summary["error"] = payload.get("error")
        if "expected_occurrences" in payload:
            summary["expected_occurrences"] = payload.get("expected_occurrences")
            summary["actual_occurrences"] = payload.get("actual_occurrences")
    return summary


def _result_replace_lines(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ok": ok,
        "path": payload.get("path"),
        "start_line": payload.get("start_line"),
        "end_line": payload.get("end_line"),
    }
    if ok is False:
        summary["error"] = payload.get("error")
    return summary


register(ToolDescriptor(
    name="write_file",
    result_kind=ToolResultKind.JSON_ENVELOPE,
    summarize_args=_args_write_file,
    summarize_result=make_json_result_summarizer(_result_write_file),
    classify_status=classify_json_envelope,
))

register(ToolDescriptor(
    name="replace_in_file",
    result_kind=ToolResultKind.JSON_ENVELOPE,
    summarize_args=_args_replace_in_file,
    summarize_result=make_json_result_summarizer(_result_replace_in_file),
    classify_status=classify_json_envelope,
))

register(ToolDescriptor(
    name="replace_lines",
    result_kind=ToolResultKind.JSON_ENVELOPE,
    summarize_args=_args_replace_lines,
    summarize_result=make_json_result_summarizer(_result_replace_lines),
    classify_status=classify_json_envelope,
))
