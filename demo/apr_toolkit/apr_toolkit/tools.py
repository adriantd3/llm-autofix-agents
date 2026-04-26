from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agents import RunContextWrapper, function_tool


@dataclass
class APRToolContext:
    """Runtime configuration for APR filesystem tools.

    All paths are resolved relative to ``root_dir``.
    """

    root_dir: str
    max_read_chars: int = 12_000
    max_search_hits: int = 50
    max_cmd_output_chars: int = 12_000
    max_file_bytes: int = 512_000
    max_list_entries: int = 400
    default_test_timeout_seconds: int = 120


# ----------------------------- helpers -----------------------------


def _ctx(wrapper: RunContextWrapper[APRToolContext]) -> APRToolContext:
    return wrapper.context


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _workspace_root(ctx: APRToolContext) -> Path:
    root = Path(ctx.root_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_path(ctx: APRToolContext, rel_path: str) -> Path:
    root = _workspace_root(ctx)
    candidate = (root / rel_path).expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path escapes workspace root: {rel_path}") from exc
    return candidate


def _safe_rel(root: Path, path: Path) -> str:
    return str(path.relative_to(root))


def _is_probably_text(path: Path) -> bool:
    mime, _ = mimetypes.guess_type(path.name)
    if mime and (mime.startswith("text/") or mime in {"application/json", "application/xml", "application/x-yaml"}):
        return True
    try:
        with path.open("rb") as f:
            chunk = f.read(4096)
        if b"\x00" in chunk:
            return False
        chunk.decode("utf-8")
        return True
    except Exception:
        return False


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def _slice_lines(lines: list[str], start_line: int | None, end_line: int | None) -> tuple[list[str], int, int]:
    start = 1 if start_line is None else max(1, start_line)
    end = len(lines) if end_line is None else min(len(lines), max(start, end_line))
    return lines[start - 1 : end], start, end


def _iter_files(root: Path, pattern: str) -> Iterable[Path]:
    for path in root.glob(pattern):
        if path.is_file():
            yield path


def _read_text_checked(cfg: APRToolContext, path: Path) -> tuple[bool, str | None, str | None]:
    if not path.exists():
        return False, "file_not_found", None
    if not path.is_file():
        return False, "not_a_file", None
    if path.stat().st_size > cfg.max_file_bytes:
        return False, "file_too_large", None
    if not _is_probably_text(path):
        return False, "binary_or_non_text", None
    return True, None, path.read_text(encoding="utf-8", errors="replace")


def _detect_test_command(root: Path) -> tuple[str, str] | None:
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


def _run_shell(cfg: APRToolContext, command: str, cwd: str = ".", timeout_seconds: int = 30) -> dict[str, Any]:
    workdir = _resolve_path(cfg, cwd)
    if not workdir.exists() or not workdir.is_dir():
        return {"ok": False, "error": "invalid_cwd", "cwd": cwd}

    try:
        completed = subprocess.run(
            ["bash", "-lc", command],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=max(1, timeout_seconds),
            env={
                **os.environ,
                "TERM": "dumb",
                "CI": "1",
                "PYTHONUNBUFFERED": "1",
                "PY_COLORS": "0",
                "NO_COLOR": "1",
            },
        )
        stdout, stdout_truncated = _truncate(completed.stdout, cfg.max_cmd_output_chars)
        stderr, stderr_truncated = _truncate(completed.stderr, cfg.max_cmd_output_chars)
        return {
            "ok": True,
            "command": command,
            "cwd": cwd,
            "exit_code": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }
    except subprocess.TimeoutExpired as exc:
        stdout, stdout_truncated = _truncate(exc.stdout or "", cfg.max_cmd_output_chars)
        stderr, stderr_truncated = _truncate(exc.stderr or "", cfg.max_cmd_output_chars)
        return {
            "ok": False,
            "error": "timeout",
            "command": command,
            "cwd": cwd,
            "timeout_seconds": timeout_seconds,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }


# ----------------------------- tools -----------------------------


@function_tool
def get_workspace_info(ctx: RunContextWrapper[APRToolContext]) -> str:
    """Return workspace limits and environment summary for the APR agent."""
    cfg = _ctx(ctx)
    root = _workspace_root(cfg)
    git_dir = (root / ".git").exists()
    test_detector = _detect_test_command(root)
    return _json(
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
    """List files under the workspace root.

    Use narrow globs like ``src/**/*.py`` whenever possible.
    """
    cfg = _ctx(ctx)
    root = _workspace_root(cfg)
    cap = max(1, min(max_entries, cfg.max_list_entries))
    entries: list[dict[str, Any]] = []
    total_seen = 0
    for path in _iter_files(root, glob):
        rel = _safe_rel(root, path)
        if not include_hidden and any(part.startswith(".") for part in Path(rel).parts):
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
                "text": _is_probably_text(path),
            }
        )
    return _json(
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
    cfg = _ctx(ctx)
    file_path = _resolve_path(cfg, path)
    ok, error, content = _read_text_checked(cfg, file_path)
    if not ok:
        return _json({"ok": False, "error": error, "path": path, "max_file_bytes": cfg.max_file_bytes})

    all_lines = content.splitlines()
    selected, start, end = _slice_lines(all_lines, start_line, end_line)
    numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(selected, start=start))
    payload, truncated = _truncate(numbered, cfg.max_read_chars)
    return _json(
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
    cfg = _ctx(ctx)
    root = _workspace_root(cfg)
    cap = max(1, min(max_results, cfg.max_search_hits))
    flags = 0 if case_sensitive else re.IGNORECASE
    matcher = re.compile(pattern if regex else re.escape(pattern), flags)

    results: list[dict[str, Any]] = []
    scanned_files = 0
    for path in _iter_files(root, glob):
        if len(results) >= cap:
            break
        try:
            if path.stat().st_size > cfg.max_file_bytes or not _is_probably_text(path):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        scanned_files += 1
        rel = _safe_rel(root, path)
        lines = text.splitlines()
        for line_no, line in enumerate(lines, start=1):
            if matcher.search(line):
                start = max(1, line_no - context_lines)
                end = min(len(lines), line_no + context_lines)
                block = "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1))
                block, block_truncated = _truncate(block, 500)
                results.append(
                    {
                        "path": rel,
                        "line": line_no,
                        "match": line.strip()[:240],
                        "context": block,
                        "context_truncated": block_truncated,
                    }
                )
                if len(results) >= cap:
                    break

    return _json(
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


@function_tool
def write_file(
    ctx: RunContextWrapper[APRToolContext],
    path: str,
    content: str,
    create_dirs: bool = True,
    overwrite: bool = True,
) -> str:
    """Write a complete text file inside the workspace."""
    cfg = _ctx(ctx)
    file_path = _resolve_path(cfg, path)
    if file_path.exists() and file_path.is_dir():
        return _json({"ok": False, "error": "path_is_directory", "path": path})
    if file_path.exists() and not overwrite:
        return _json({"ok": False, "error": "file_exists", "path": path})
    if create_dirs:
        file_path.parent.mkdir(parents=True, exist_ok=True)
    elif not file_path.parent.exists():
        return _json({"ok": False, "error": "parent_missing", "path": path})
    file_path.write_text(content, encoding="utf-8")
    return _json({"ok": True, "path": path, "bytes_written": len(content.encode("utf-8"))})


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
    cfg = _ctx(ctx)
    file_path = _resolve_path(cfg, path)
    ok, error, original = _read_text_checked(cfg, file_path)
    if not ok:
        return _json({"ok": False, "error": error, "path": path})

    occurrences = original.count(old)
    if expected_occurrences is not None and occurrences != expected_occurrences:
        return _json(
            {
                "ok": False,
                "error": "unexpected_occurrence_count",
                "path": path,
                "expected_occurrences": expected_occurrences,
                "actual_occurrences": occurrences,
            }
        )
    if occurrences == 0:
        return _json({"ok": False, "error": "old_text_not_found", "path": path})

    updated = original.replace(old, new) if replace_all else original.replace(old, new, 1)
    file_path.write_text(updated, encoding="utf-8")
    return _json(
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
    cfg = _ctx(ctx)
    file_path = _resolve_path(cfg, path)
    ok, error, original = _read_text_checked(cfg, file_path)
    if not ok:
        return _json({"ok": False, "error": error, "path": path})

    lines = original.splitlines(keepends=True)
    if not lines and start_line == 1 and end_line == 1:
        lines = []
    if start_line < 1 or end_line < start_line or end_line > max(len(lines), 1):
        return _json(
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
    return _json({"ok": True, "path": path, "start_line": start_line, "end_line": end_line})


@function_tool
def execute_command(
    ctx: RunContextWrapper[APRToolContext],
    command: str,
    cwd: str = ".",
    timeout_seconds: int = 30,
) -> str:
    """Run a non-interactive shell command as `bash -lc <command>`."""
    cfg = _ctx(ctx)
    return _json(_run_shell(cfg, command=command, cwd=cwd, timeout_seconds=timeout_seconds))


@function_tool
def run_test_target(
    ctx: RunContextWrapper[APRToolContext],
    target: str | None = None,
    runner: str | None = None,
    cwd: str = ".",
    timeout_seconds: int | None = None,
) -> str:
    """Run a focused test command.

    If ``runner`` is omitted, the tool tries to detect a suitable test command.
    ``target`` is appended to the detected runner command.
    """
    cfg = _ctx(ctx)
    root = _workspace_root(cfg)
    if runner is None:
        detected = _detect_test_command(root)
        if detected is None:
            return _json({"ok": False, "error": "no_test_runner_detected"})
        runner = detected[1]
    command = runner if not target else f"{runner} {target}"
    timeout = timeout_seconds or cfg.default_test_timeout_seconds
    result = _run_shell(cfg, command=command, cwd=cwd, timeout_seconds=timeout)
    result["tool"] = "run_test_target"
    result["target"] = target
    result["runner"] = runner
    return _json(result)


@function_tool
def git_status_summary(
    ctx: RunContextWrapper[APRToolContext],
    cwd: str = ".",
) -> str:
    """Return a compact git status summary for the workspace."""
    cfg = _ctx(ctx)
    status = _run_shell(cfg, "git status --short --branch", cwd=cwd, timeout_seconds=20)
    if not status.get("ok"):
        return _json(status)
    if status.get("exit_code") != 0:
        return _json({"ok": False, "error": "git_status_failed", **status})
    lines = [line for line in status["stdout"].splitlines() if line.strip()]
    branch = lines[0] if lines else ""
    changes = lines[1:] if len(lines) > 1 else []
    return _json(
        {
            "ok": True,
            "branch": branch,
            "changed_files": len(changes),
            "changes": changes[:100],
            "truncated": len(changes) > 100,
        }
    )


@function_tool
def git_diff_summary(
    ctx: RunContextWrapper[APRToolContext],
    pathspec: str | None = None,
    cwd: str = ".",
) -> str:
    """Return a compact git diff summary and truncated patch text."""
    cfg = _ctx(ctx)
    summary_cmd = "git diff --stat"
    patch_cmd = "git diff --unified=3 --minimal"
    if pathspec:
        summary_cmd += f" -- {pathspec}"
        patch_cmd += f" -- {pathspec}"
    summary = _run_shell(cfg, summary_cmd, cwd=cwd, timeout_seconds=20)
    patch = _run_shell(cfg, patch_cmd, cwd=cwd, timeout_seconds=20)
    if summary.get("exit_code") != 0:
        return _json({"ok": False, "error": "git_diff_failed", "summary": summary, "patch": patch})
    patch_text, patch_truncated = _truncate(patch.get("stdout", ""), cfg.max_read_chars)
    return _json(
        {
            "ok": True,
            "pathspec": pathspec,
            "summary": summary.get("stdout", ""),
            "patch": patch_text,
            "patch_truncated": patch_truncated,
        }
    )


@function_tool
def apply_unified_diff(
    ctx: RunContextWrapper[APRToolContext],
    diff: str,
    cwd: str = ".",
    strip: int = 0,
    check_only: bool = False,
) -> str:
    """Apply a unified diff from a string using the system `patch` command."""
    cfg = _ctx(ctx)
    workdir = _resolve_path(cfg, cwd)
    if shutil.which("patch") is None:
        return _json({"ok": False, "error": "patch_command_not_found"})

    args = ["patch", f"-p{max(0, strip)}", "--forward", "--batch"]
    if check_only:
        args.append("--dry-run")
    try:
        completed = subprocess.run(
            args,
            cwd=str(workdir),
            input=diff,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "TERM": "dumb", "CI": "1", "NO_COLOR": "1"},
        )
    except subprocess.TimeoutExpired as exc:
        stdout, stdout_truncated = _truncate(exc.stdout or "", cfg.max_cmd_output_chars)
        stderr, stderr_truncated = _truncate(exc.stderr or "", cfg.max_cmd_output_chars)
        return _json(
            {
                "ok": False,
                "error": "timeout",
                "stdout": stdout,
                "stderr": stderr,
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated,
            }
        )

    stdout, stdout_truncated = _truncate(completed.stdout, cfg.max_cmd_output_chars)
    stderr, stderr_truncated = _truncate(completed.stderr, cfg.max_cmd_output_chars)
    return _json(
        {
            "ok": completed.returncode == 0,
            "exit_code": completed.returncode,
            "cwd": cwd,
            "check_only": check_only,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }
    )


APR_FUNCTION_TOOLS = [
    get_workspace_info,
    list_files,
    read_file,
    search_files,
    write_file,
    replace_in_file,
    replace_lines,
    execute_command,
    run_test_target,
    git_status_summary,
    git_diff_summary,
    apply_unified_diff,
]


APR_CORE_TOOLS = [
    get_workspace_info,
    list_files,
    read_file,
    search_files,
    replace_in_file,
    replace_lines,
    execute_command,
    run_test_target,
]


APR_SAFE_MINIMAL_TOOLS = [
    read_file,
    search_files,
    replace_in_file,
    execute_command,
]


def build_apr_tools(profile: str = "full") -> list[Any]:
    """Return a predefined APR tool profile.

    Profiles:
        - ``minimal``: smallest token/tool surface.
        - ``core``: better default for APR loops.
        - ``full``: includes git and unified-diff helpers.
    """
    profiles = {
        "minimal": APR_SAFE_MINIMAL_TOOLS,
        "core": APR_CORE_TOOLS,
        "full": APR_FUNCTION_TOOLS,
    }
    try:
        return list(profiles[profile])
    except KeyError as exc:
        raise ValueError(f"Unknown APR tool profile: {profile}") from exc
