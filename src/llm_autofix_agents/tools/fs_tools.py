from __future__ import annotations

import re
import shutil
from dataclasses import asdict
from typing import Any

from agents import RunContextWrapper, function_tool

from llm_autofix_agents.tools.context import APRToolContext, get_tool_context
from llm_autofix_agents.tools.paths import iter_files, resolve_path, safe_rel, workspace_root
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
    """Return workspace limits and environment summary for the APR agent."""
    cfg = get_tool_context(ctx)
    root = workspace_root(cfg)
    git_dir = (root / ".git").exists()
    test_detector = detect_test_command(root)
    return json_result(
        {
            "ok": True,
            "root_dir": str(root),
            "config": asdict(cfg),
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
    entries: list[dict[str, Any]] = []
    total_seen = 0
    for path in iter_files(root, glob):
        rel = safe_rel(root, path)
        if not include_hidden and any(part.startswith(".") for part in rel.split("/")):
            continue
        total_seen += 1
        if len(entries) >= cap:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        entries.append(
            {
                "path": rel,
                "bytes": stat.st_size,
                "text": is_probably_text(path),
            }
        )
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
    """Read a text file inside the workspace with line numbers."""
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
    """Search text files in the workspace for a literal string or regex."""
    cfg = get_tool_context(ctx)
    root = workspace_root(cfg)
    cap = max(1, min(max_results, cfg.max_search_hits))
    flags = 0 if case_sensitive else re.IGNORECASE
    matcher = re.compile(pattern if regex else re.escape(pattern), flags)

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
