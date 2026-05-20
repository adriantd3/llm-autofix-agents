from __future__ import annotations

import re
import shutil
from typing import Any, Mapping

from agents import RunContextWrapper, function_tool

from llm_autofix_agents.tools.context import APRToolContext, get_tool_context
from llm_autofix_agents.tools.metadata import (
    ToolDescriptor,
    ToolResultKind,
    classify_json_envelope,
    content_hash,
    make_json_result_summarizer,
)
from llm_autofix_agents.tools.paths import iter_files, resolve_path, safe_rel, workspace_root
from llm_autofix_agents.tools.registry import register
from llm_autofix_agents.tools.serialization import json_result
from llm_autofix_agents.tools.text import (
    detect_test_command,
    is_probably_text,
    read_text_checked,
    slice_lines,
    truncate,
)


@function_tool
def get_workspace_info(ctx: RunContextWrapper[APRToolContext]) -> str:
    """Return workspace root path, Python location, and git status."""
    cfg = get_tool_context(ctx)
    root = workspace_root(cfg)
    git_dir = (root / ".git").exists()
    test_detector = detect_test_command(root)
    return json_result(
        {
            "ok": True,
            "root_dir": str(root),
            "python": shutil.which("python") or shutil.which("python3"),
            "git_repo": git_dir,
            "suggested_test_runner": test_detector[1] if test_detector else None,
        }
    )


@function_tool
def list_files(
    ctx: RunContextWrapper[APRToolContext],
    glob: str = "**/*",
    include_hidden: bool = False,
    max_entries: int = 200,
) -> str:
    """List files under the workspace root."""
    cfg = get_tool_context(ctx)
    root = workspace_root(cfg)
    cap = max(1, min(max_entries, cfg.max_list_entries))
    entries: list[str] = []
    total_seen = 0
    for path in iter_files(root, glob):
        rel = safe_rel(root, path)
        if not include_hidden and any(part.startswith(".") for part in rel.split("/")):
            continue
        total_seen += 1
        if len(entries) < cap:
            entries.append(rel)
    return json_result(
        {
            "ok": True,
            "glob": glob,
            "returned": len(entries),
            "total_seen": total_seen,
            "truncated": total_seen > len(entries),
            "entries": entries,
        }
    )


@function_tool
def read_file(
    ctx: RunContextWrapper[APRToolContext],
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    """Read a text file from the workspace with line numbers. Paths relative to workspace root.

    Use start_line/end_line for large files. Returned lines are numbered — copy them verbatim into replace_in_file.
    """
    cfg = get_tool_context(ctx)
    file_path = resolve_path(cfg, path)
    ok, error, content = read_text_checked(cfg, file_path)
    if not ok:
        return json_result({"ok": False, "error": error, "path": path, "max_file_bytes": cfg.max_file_bytes})

    all_lines = (content or "").splitlines()
    selected, start, end = slice_lines(all_lines, start_line, end_line)
    numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(selected, start=start))
    payload, truncated = truncate(numbered, cfg.max_read_chars)
    return json_result(
        {
            "ok": True,
            "path": path,
            "start_line": start,
            "end_line": end,
            "line_count": len(all_lines),
            "truncated": truncated,
            "content": payload,
        }
    )


@function_tool
def search_files(
    ctx: RunContextWrapper[APRToolContext],
    pattern: str,
    glob: str = "**/*",
    regex: bool = False,
    case_sensitive: bool = False,
    context_lines: int = 0,
    max_results: int = 20,
) -> str:
    """Search text files for a literal string or regex pattern.

    glob controls which files are scanned — use **/*.py to search all .py files recursively;
    *.py matches only root-level files. Set regex=True for ^, $, |, \\d, etc.
    """
    cfg = get_tool_context(ctx)

    # Normalize pattern based on case_sensitive: two calls that produce identical
    # results (same case-insensitive pattern, same glob, same regex mode) are
    # treated as the same query. case_sensitive=True keeps the original casing.
    norm_pattern = pattern if case_sensitive else pattern.lower()
    query_key = f"{norm_pattern}|{glob}|r={regex}|cs={case_sensitive}"

    # Exact duplicate detection: same effective query already searched this iteration.
    prev_call = cfg.seen_search_queries.get(query_key)
    if prev_call is not None:
        return json_result({
            "ok": False,
            "error": (
                f"duplicate_search: pattern={pattern!r} glob={glob!r} was already searched "
                f"in tool call #{prev_call} this iteration. "
                "The result is in your context — use it instead of calling again."
            ),
        })

    # Hard pre-edit search budget: block further searches once exhausted.
    # Lifted as soon as any code edit is made (iteration_edit_count > 0).
    if cfg.search_files_budget > 0 and cfg.iteration_edit_count == 0:
        if cfg.search_files_calls >= cfg.search_files_budget:
            return json_result({
                "ok": False,
                "error": (
                    f"search_budget_exhausted: {cfg.search_files_calls} search_files calls made "
                    "with 0 code edits this iteration. "
                    "Apply your best hypothesis with replace_in_file, or report status=stuck."
                ),
            })

    # Compile the matcher BEFORE registering the call so that an invalid regex
    # returns a clean error without consuming a search slot. re.escape() never
    # raises, so this only guards the regex=True path.
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        matcher = re.compile(pattern if regex else re.escape(pattern), flags)
    except re.error as exc:
        return json_result({"ok": False, "error": f"invalid_regex: {exc}"})

    cfg.seen_search_queries[query_key] = cfg.iteration_tool_call_count
    cfg.search_files_calls += 1

    root = workspace_root(cfg)
    cap = max(1, min(max_results, cfg.max_search_hits))
    # flags and matcher already computed above

    results: list[dict[str, Any]] = []
    scanned_files = 0
    for path in iter_files(root, glob):
        if len(results) >= cap:
            break
        try:
            if path.stat().st_size > cfg.max_file_bytes or not is_probably_text(path):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        scanned_files += 1
        rel = safe_rel(root, path)
        lines = text.splitlines()
        for line_no, line in enumerate(lines, start=1):
            if matcher.search(line):
                start = max(1, line_no - context_lines)
                end = min(len(lines), line_no + context_lines)
                block = "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1))
                snippet, block_truncated = truncate(block, 500)
                results.append(
                    {
                        "path": rel,
                        "line": line_no,
                        "match": line.strip()[:240],
                        "context": snippet,
                        "context_truncated": block_truncated,
                    }
                )
                if len(results) >= cap:
                    break

    return json_result(
        {
            "ok": True,
            "pattern": pattern,
            "glob": glob,
            "regex": regex,
            "case_sensitive": case_sensitive,
            "returned": len(results),
            "scanned_files": scanned_files,
            "results": results,
        }
    )


# ---------------------------------------------------------------------------
# Observability metadata (SH1)
# ---------------------------------------------------------------------------


def _args_get_workspace_info(args: Mapping[str, Any]) -> dict[str, Any]:
    return {}


def _args_list_files(args: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "glob": args.get("glob"),
        "include_hidden": args.get("include_hidden", False),
        "max_entries": args.get("max_entries"),
    }


def _args_read_file(args: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": args.get("path"),
        "start_line": args.get("start_line"),
        "end_line": args.get("end_line"),
    }


def _args_search_files(args: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "pattern": args.get("pattern"),
        "glob": args.get("glob"),
        "regex": args.get("regex"),
        "max_results": args.get("max_results"),
    }


def _result_get_workspace_info(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    return {"ok": ok, "root_dir": payload.get("root_dir")}


def _result_list_files(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    return {
        "ok": ok,
        "glob": payload.get("glob"),
        "returned": payload.get("returned"),
        "total_seen": payload.get("total_seen"),
        "truncated": payload.get("truncated"),
    }


def _result_read_file(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ok": ok,
        "path": payload.get("path"),
        "start_line": payload.get("start_line"),
        "end_line": payload.get("end_line"),
        "line_count": payload.get("line_count"),
        "truncated": payload.get("truncated"),
        "content_chars": len(payload.get("content", "")),
    }
    c = payload.get("content", "")
    if c:
        summary["content_hash"] = content_hash(c)
    if ok is False:
        summary["error"] = payload.get("error")
        summary["max_file_bytes"] = payload.get("max_file_bytes")
    return summary


def _result_search_files(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    results = payload.get("results", [])
    top_paths = [r.get("path", "") for r in results[:5] if isinstance(r, dict)]
    return {
        "ok": ok,
        "pattern": payload.get("pattern"),
        "glob": payload.get("glob"),
        "returned": payload.get("returned"),
        "scanned_files": payload.get("scanned_files"),
        "top_paths": top_paths,
    }


register(ToolDescriptor(
    name="get_workspace_info",
    result_kind=ToolResultKind.JSON_ENVELOPE,
    summarize_args=_args_get_workspace_info,
    summarize_result=make_json_result_summarizer(_result_get_workspace_info),
    classify_status=classify_json_envelope,
))

register(ToolDescriptor(
    name="list_files",
    result_kind=ToolResultKind.JSON_ENVELOPE,
    summarize_args=_args_list_files,
    summarize_result=make_json_result_summarizer(_result_list_files),
    classify_status=classify_json_envelope,
))

register(ToolDescriptor(
    name="read_file",
    result_kind=ToolResultKind.JSON_ENVELOPE,
    summarize_args=_args_read_file,
    summarize_result=make_json_result_summarizer(_result_read_file),
    classify_status=classify_json_envelope,
))

register(ToolDescriptor(
    name="search_files",
    result_kind=ToolResultKind.JSON_ENVELOPE,
    summarize_args=_args_search_files,
    summarize_result=make_json_result_summarizer(_result_search_files),
    classify_status=classify_json_envelope,
))
