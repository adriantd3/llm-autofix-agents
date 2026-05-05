from __future__ import annotations

import hashlib
import json
from typing import Any

_MAX_STRING = 500
_EXCERPT_LENGTH = 200


def _truncate(value: str, max_len: int = _MAX_STRING) -> str:
    if len(value) <= max_len:
        return value
    return value[:max_len] + "... [truncated]"


def _content_hash(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def summarize_tool_result(tool_name: str, result: str) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return {"ok": None, "error_summary": _truncate(result, _EXCERPT_LENGTH)}

    if not isinstance(payload, dict):
        return {"ok": None, "raw_type": type(payload).__name__}

    ok = payload.get("ok")

    if tool_name == "read_file":
        return _summarize_read_file(payload, ok)
    if tool_name == "search_files":
        return _summarize_search_files(payload, ok)
    if tool_name == "replace_in_file":
        return _summarize_replace_in_file(payload, ok)
    if tool_name == "replace_lines":
        return _summarize_replace_lines(payload, ok)
    if tool_name == "write_file":
        return _summarize_write_file(payload, ok)
    if tool_name in ("execute_command", "run_test_target"):
        return _summarize_command_result(payload, ok, tool_name)
    if tool_name == "git_status_summary":
        return _summarize_git_status(payload, ok)
    if tool_name == "git_diff_summary":
        return _summarize_git_diff(payload, ok)
    if tool_name == "list_files":
        return _summarize_list_files(payload, ok)
    if tool_name == "get_workspace_info":
        return {"ok": ok, "root_dir": payload.get("root_dir")}
    if tool_name == "apply_unified_diff":
        return _summarize_apply_diff(payload, ok)

    return {"ok": ok, "error": payload.get("error")}


def _summarize_read_file(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ok": ok,
        "path": payload.get("path"),
        "start_line": payload.get("start_line"),
        "end_line": payload.get("end_line"),
        "line_count": payload.get("line_count"),
        "truncated": payload.get("truncated"),
        "content_chars": len(payload.get("content", "")),
    }
    content = payload.get("content", "")
    if content:
        summary["content_hash"] = _content_hash(content)
    if ok is False:
        summary["error"] = payload.get("error")
        summary["max_file_bytes"] = payload.get("max_file_bytes")
    return summary


def _summarize_search_files(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
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


def _summarize_replace_in_file(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ok": ok,
        "path": payload.get("path"),
    }
    if ok is True:
        summary["replaced"] = payload.get("replaced")
        summary["bytes_written"] = payload.get("bytes_written")
    else:
        summary["error"] = payload.get("error")
        if "expected_occurrences" in payload:
            summary["expected_occurrences"] = payload.get("expected_occurrences")
            summary["actual_occurrences"] = payload.get("actual_occurrences")
    return summary


def _summarize_replace_lines(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ok": ok,
        "path": payload.get("path"),
        "start_line": payload.get("start_line"),
        "end_line": payload.get("end_line"),
    }
    if ok is False:
        summary["error"] = payload.get("error")
    return summary


def _summarize_write_file(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ok": ok,
        "path": payload.get("path"),
    }
    if ok is True:
        summary["bytes_written"] = payload.get("bytes_written")
    else:
        summary["error"] = payload.get("error")
    return summary


def _summarize_command_result(payload: dict[str, Any], ok: Any, tool_name: str) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ok": ok,
        "exit_code": payload.get("exit_code"),
        "timed_out": payload.get("timed_out"),
        "tool": tool_name,
    }
    command = payload.get("command", "")
    if command:
        summary["command"] = _truncate(str(command), 200)
    cwd = payload.get("cwd")
    if cwd:
        summary["cwd"] = cwd
    if tool_name == "run_test_target":
        summary["target"] = payload.get("target")
        summary["runner"] = payload.get("runner")
    stdout = payload.get("stdout", "")
    stderr = payload.get("stderr", "")
    if stdout:
        summary["stdout_chars"] = len(str(stdout))
    if stderr:
        summary["stderr_chars"] = len(str(stderr))
    if ok is False:
        summary["error"] = payload.get("error")
    return summary


def _summarize_git_status(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ok": ok,
    }
    if ok is True:
        summary["branch"] = payload.get("branch")
        summary["changed_files"] = payload.get("changed_files")
        summary["truncated"] = payload.get("truncated")
    else:
        summary["error"] = payload.get("error")
    return summary


def _summarize_git_diff(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ok": ok,
        "pathspec": payload.get("pathspec"),
    }
    if ok is True:
        summary["patch_truncated"] = payload.get("patch_truncated")
    else:
        summary["error"] = payload.get("error")
    return summary


def _summarize_list_files(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    return {
        "ok": ok,
        "glob": payload.get("glob"),
        "returned": payload.get("returned"),
        "total_seen": payload.get("total_seen"),
        "truncated": payload.get("truncated"),
    }


def _summarize_apply_diff(payload: dict[str, Any], ok: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {"ok": ok}
    if "path" in payload:
        summary["path"] = payload.get("path")
    if ok is False:
        summary["error"] = payload.get("error")
    return summary


def summarize_tool_args(tool_name: str, parsed_args: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "read_file":
        return _args_read_file(parsed_args)
    if tool_name == "search_files":
        return _args_search_files(parsed_args)
    if tool_name == "replace_in_file":
        return _args_replace_in_file(parsed_args)
    if tool_name == "replace_lines":
        return _args_replace_lines(parsed_args)
    if tool_name == "write_file":
        return _args_write_file(parsed_args)
    if tool_name in ("execute_command", "run_test_target"):
        return _args_command(parsed_args, tool_name)
    if tool_name in ("git_status_summary", "git_diff_summary"):
        return _args_git(parsed_args, tool_name)
    if tool_name == "list_files":
        return _args_list_files(parsed_args)
    if tool_name == "get_workspace_info":
        return {"tool": tool_name}
    if tool_name == "apply_unified_diff":
        return _args_apply_diff(parsed_args)
    return {"tool": tool_name, "arg_count": len(parsed_args)}


def _args_read_file(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": args.get("path"),
        "start_line": args.get("start_line"),
        "end_line": args.get("end_line"),
    }


def _args_search_files(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "pattern": args.get("pattern"),
        "glob": args.get("glob"),
        "regex": args.get("regex"),
        "max_results": args.get("max_results"),
    }


def _args_replace_in_file(args: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": args.get("path"),
        "replace_all": args.get("replace_all", False),
        "expected_occurrences": args.get("expected_occurrences"),
    }
    old = args.get("old", "")
    if old:
        summary["old_hash"] = _content_hash(old)
        summary["old_length"] = len(old)
    new = args.get("new", "")
    if new:
        summary["new_hash"] = _content_hash(new)
        summary["new_length"] = len(new)
    return summary


def _args_replace_lines(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": args.get("path"),
        "start_line": args.get("start_line"),
        "end_line": args.get("end_line"),
        "new_lines_length": len(args.get("new_lines", "")),
    }


def _args_write_file(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": args.get("path"),
        "content_length": len(args.get("content", "")),
        "create_dirs": args.get("create_dirs", True),
        "overwrite": args.get("overwrite", True),
    }


def _args_command(args: dict[str, Any], tool_name: str) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "tool": tool_name,
    }
    command = args.get("command", "")
    summary["command"] = _truncate(str(command), 200)
    if "cwd" in args:
        summary["cwd"] = args.get("cwd")
    if "timeout_seconds" in args:
        summary["timeout_seconds"] = args.get("timeout_seconds")
    if tool_name == "run_test_target":
        if "target" in args:
            summary["target"] = args.get("target")
        if "runner" in args:
            summary["runner"] = args.get("runner")
    return summary


def _args_git(args: dict[str, Any], tool_name: str) -> dict[str, Any]:
    summary: dict[str, Any] = {"tool": tool_name}
    if "cwd" in args:
        summary["cwd"] = args.get("cwd")
    if "pathspec" in args:
        summary["pathspec"] = args.get("pathspec")
    return summary


def _args_list_files(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "glob": args.get("glob"),
        "include_hidden": args.get("include_hidden", False),
        "max_entries": args.get("max_entries"),
    }


def _args_apply_diff(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": args.get("path"),
        "diff_length": len(args.get("diff_content", "")),
    }
