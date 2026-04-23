from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from llm_autofix_agents.llm.provider import AgentFixIterationRecord


def normalize_paths(paths: list[str]) -> list[str]:
    return sorted(path.replace("\\", "/") for path in paths)


def validate_changed_files_coherence(
    *,
    proposal: AgentFixIterationRecord,
    changed_files: list[str],
    repo_changed: bool,
    diff: str,
) -> tuple[bool, dict[str, Any]]:
    proposal_files = normalize_paths(proposal.changed_files)
    observed_files = normalize_paths(changed_files)

    should_validate = repo_changed or bool(diff)
    if not should_validate:
        return True, {
            "checked": False,
            "proposal_changed_files": proposal_files,
            "observed_changed_files": observed_files,
        }

    is_match = proposal_files == observed_files
    return is_match, {
        "checked": True,
        "proposal_changed_files": proposal_files,
        "observed_changed_files": observed_files,
    }


def validate_diff_integrity(*, changed_files: list[str], diff: str) -> tuple[bool, str]:
    if changed_files and not diff.strip():
        return False, "changed_files_detected_but_diff_is_empty"
    return True, "ok"


def persist_iteration_artifacts(
    *,
    repo_root: Path,
    run_id: str,
    iteration: int,
    diff: str,
    changed_files: list[str],
    temp_branch: str | None = None,
    ignore_rules: list[str] | None = None,
) -> dict[str, Any]:
    artifacts_dir = repo_root / "results" / run_id / f"it{iteration:02d}"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    run_dir = artifacts_dir.parent

    diff_path = artifacts_dir / "patch.diff"
    changed_files_path = artifacts_dir / "changed_files.json"
    metadata_path = artifacts_dir / "metadata.json"
    file_changes_path = artifacts_dir / "file_changes.json"
    patch_summary_path = artifacts_dir / "patch_summary.json"
    manifest_path = run_dir / "manifest.json"

    diff_path.write_text(diff, encoding="utf-8")
    changed_files_path.write_text(json.dumps(changed_files, indent=2, ensure_ascii=True), encoding="utf-8")

    metadata = {
        "run_id": run_id,
        "iteration": iteration,
        "generated_at": datetime.now(UTC).isoformat(),
        "changed_files_count": len(changed_files),
        "diff_bytes": len(diff.encode("utf-8")),
        "diff_sha256": sha256(diff.encode("utf-8")).hexdigest(),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=True), encoding="utf-8")

    file_changes = _extract_file_changes(diff=diff, changed_files=changed_files)
    file_changes_path.write_text(json.dumps(file_changes, indent=2, ensure_ascii=True), encoding="utf-8")

    patch_summary = {
        "run_id": run_id,
        "iteration": iteration,
        "generated_at": metadata["generated_at"],
        "temp_branch": temp_branch,
        "changed_files_count": len(changed_files),
        "diff_bytes": metadata["diff_bytes"],
        "diff_sha256": metadata["diff_sha256"],
        "ignore_rules": ignore_rules if ignore_rules is not None else [],
        "totals": {
            "added_lines": sum(entry["added_lines"] for entry in file_changes),
            "deleted_lines": sum(entry["deleted_lines"] for entry in file_changes),
        },
        "files": file_changes,
    }
    patch_summary_path.write_text(json.dumps(patch_summary, indent=2, ensure_ascii=True), encoding="utf-8")

    manifest = _load_or_create_manifest(manifest_path=manifest_path, run_id=run_id)
    file_traces = _build_file_trace_for_manifest(file_changes=file_changes, iteration=iteration)
    iteration_entry = {
        "iteration": iteration,
        "directory": artifacts_dir.relative_to(repo_root).as_posix(),
        "diff_file": diff_path.relative_to(repo_root).as_posix(),
        "changed_files_file": changed_files_path.relative_to(repo_root).as_posix(),
        "metadata_file": metadata_path.relative_to(repo_root).as_posix(),
        "file_changes_file": file_changes_path.relative_to(repo_root).as_posix(),
        "patch_summary_file": patch_summary_path.relative_to(repo_root).as_posix(),
        "changed_files_count": len(changed_files),
        "diff_bytes": metadata["diff_bytes"],
        "diff_sha256": metadata["diff_sha256"],
        "timestamp": metadata["generated_at"],
    }
    _upsert_iteration_entry(manifest=manifest, entry=iteration_entry)
    manifest["updated_at"] = datetime.now(UTC).isoformat()
    manifest["iterations_count"] = len(manifest["iterations"])
    existing_files = manifest.get("files")
    if not isinstance(existing_files, dict):
        existing_files = {}
    manifest["files"] = _merge_manifest_file_traces(
        existing=existing_files,
        new=file_traces,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")

    return {
        "directory": artifacts_dir.relative_to(repo_root).as_posix(),
        "diff_file": diff_path.relative_to(repo_root).as_posix(),
        "changed_files_file": changed_files_path.relative_to(repo_root).as_posix(),
        "metadata_file": metadata_path.relative_to(repo_root).as_posix(),
        "file_changes_file": file_changes_path.relative_to(repo_root).as_posix(),
        "patch_summary_file": patch_summary_path.relative_to(repo_root).as_posix(),
        "manifest_file": manifest_path.relative_to(repo_root).as_posix(),
        "changed_files_count": len(changed_files),
        "diff_bytes": metadata["diff_bytes"],
        "diff_sha256": metadata["diff_sha256"],
        "temp_branch": temp_branch,
    }


def _load_or_create_manifest(*, manifest_path: Path, run_id: str) -> dict[str, Any]:
    if not manifest_path.exists():
        now = datetime.now(UTC).isoformat()
        return {
            "run_id": run_id,
            "created_at": now,
            "updated_at": now,
            "iterations_count": 0,
            "iterations": [],
        }

    try:
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        now = datetime.now(UTC).isoformat()
        return {
            "run_id": run_id,
            "created_at": now,
            "updated_at": now,
            "iterations_count": 0,
            "iterations": [],
        }

    if not isinstance(loaded, dict):
        now = datetime.now(UTC).isoformat()
        return {
            "run_id": run_id,
            "created_at": now,
            "updated_at": now,
            "iterations_count": 0,
            "iterations": [],
        }

    iterations = loaded.get("iterations")
    if not isinstance(iterations, list):
        loaded["iterations"] = []

    loaded.setdefault("run_id", run_id)
    loaded.setdefault("created_at", datetime.now(UTC).isoformat())
    loaded.setdefault("updated_at", datetime.now(UTC).isoformat())
    loaded.setdefault("iterations_count", len(loaded["iterations"]))
    return loaded


def _upsert_iteration_entry(*, manifest: dict[str, Any], entry: dict[str, Any]) -> None:
    iterations = manifest["iterations"]
    for index, existing in enumerate(iterations):
        if isinstance(existing, dict) and existing.get("iteration") == entry["iteration"]:
            iterations[index] = entry
            return
    iterations.append(entry)
    iterations.sort(key=lambda item: item.get("iteration", 0) if isinstance(item, dict) else 0)


def _extract_file_changes(*, diff: str, changed_files: list[str]) -> list[dict[str, Any]]:
    changes_by_path: dict[str, dict[str, Any]] = {}
    current_path: str | None = None

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            parts = line.split(" ")
            if len(parts) >= 4:
                current_path = parts[3].removeprefix("b/").strip()
                changes_by_path[current_path] = {
                    "path": current_path,
                    "status": "modified",
                    "added_lines": 0,
                    "deleted_lines": 0,
                }
            continue

        if current_path is None:
            continue

        if line.startswith("new file mode"):
            changes_by_path[current_path]["status"] = "added"
            continue
        if line.startswith("deleted file mode"):
            changes_by_path[current_path]["status"] = "deleted"
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            changes_by_path[current_path]["added_lines"] += 1
            continue
        if line.startswith("-"):
            changes_by_path[current_path]["deleted_lines"] += 1

    for path in changed_files:
        normalized = path.replace("\\", "/")
        if normalized not in changes_by_path:
            changes_by_path[normalized] = {
                "path": normalized,
                "status": "modified",
                "added_lines": 0,
                "deleted_lines": 0,
            }

    entries = list(changes_by_path.values())
    entries.sort(key=lambda item: item["path"])
    return entries


def _build_file_trace_for_manifest(*, file_changes: list[dict[str, Any]], iteration: int) -> dict[str, dict[str, Any]]:
    traces: dict[str, dict[str, Any]] = {}
    for item in file_changes:
        path = str(item["path"])
        traces[path] = {
            "path": path,
            "first_seen_iteration": iteration,
            "last_seen_iteration": iteration,
            "total_added_lines": int(item["added_lines"]),
            "total_deleted_lines": int(item["deleted_lines"]),
            "latest_status": item["status"],
        }
    return traces


def _merge_manifest_file_traces(
    *,
    existing: dict[str, Any],
    new: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for path, current in existing.items():
        if not isinstance(path, str) or not isinstance(current, dict):
            continue
        merged[path] = {
            "path": path,
            "first_seen_iteration": int(current.get("first_seen_iteration", 0)),
            "last_seen_iteration": int(current.get("last_seen_iteration", 0)),
            "total_added_lines": int(current.get("total_added_lines", 0)),
            "total_deleted_lines": int(current.get("total_deleted_lines", 0)),
            "latest_status": str(current.get("latest_status", "modified")),
        }

    for path, item in new.items():
        if path not in merged:
            merged[path] = item
            continue
        merged[path]["first_seen_iteration"] = min(merged[path]["first_seen_iteration"], item["first_seen_iteration"])
        merged[path]["last_seen_iteration"] = max(merged[path]["last_seen_iteration"], item["last_seen_iteration"])
        merged[path]["total_added_lines"] += item["total_added_lines"]
        merged[path]["total_deleted_lines"] += item["total_deleted_lines"]
        merged[path]["latest_status"] = item["latest_status"]

    return dict(sorted(merged.items(), key=lambda entry: entry[0]))
