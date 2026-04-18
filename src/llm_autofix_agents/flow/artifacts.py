from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from llm_autofix_agents.llm.provider import AgentFixProposal


def normalize_paths(paths: list[str]) -> list[str]:
    return sorted(path.replace("\\", "/") for path in paths)


def validate_changed_files_coherence(
    *,
    proposal: AgentFixProposal,
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
) -> dict[str, Any]:
    artifacts_dir = repo_root / "results" / run_id / f"it{iteration:02d}"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    run_dir = artifacts_dir.parent

    diff_path = artifacts_dir / "patch.diff"
    changed_files_path = artifacts_dir / "changed_files.json"
    metadata_path = artifacts_dir / "metadata.json"
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

    manifest = _load_or_create_manifest(manifest_path=manifest_path, run_id=run_id)
    iteration_entry = {
        "iteration": iteration,
        "directory": artifacts_dir.relative_to(repo_root).as_posix(),
        "diff_file": diff_path.relative_to(repo_root).as_posix(),
        "changed_files_file": changed_files_path.relative_to(repo_root).as_posix(),
        "metadata_file": metadata_path.relative_to(repo_root).as_posix(),
        "changed_files_count": len(changed_files),
        "diff_bytes": metadata["diff_bytes"],
        "diff_sha256": metadata["diff_sha256"],
        "timestamp": metadata["generated_at"],
    }
    _upsert_iteration_entry(manifest=manifest, entry=iteration_entry)
    manifest["updated_at"] = datetime.now(UTC).isoformat()
    manifest["iterations_count"] = len(manifest["iterations"])
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")

    return {
        "directory": artifacts_dir.relative_to(repo_root).as_posix(),
        "diff_file": diff_path.relative_to(repo_root).as_posix(),
        "changed_files_file": changed_files_path.relative_to(repo_root).as_posix(),
        "metadata_file": metadata_path.relative_to(repo_root).as_posix(),
        "manifest_file": manifest_path.relative_to(repo_root).as_posix(),
        "changed_files_count": len(changed_files),
        "diff_bytes": metadata["diff_bytes"],
        "diff_sha256": metadata["diff_sha256"],
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
