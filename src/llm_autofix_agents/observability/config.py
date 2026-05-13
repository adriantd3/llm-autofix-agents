from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ObservabilityConfig:
    enabled: bool
    interactive: bool
    results_dir: Path
    live_log_enabled: bool
    jsonl_enabled: bool = True
    # None → observer_factory computes per-run path: results_dir / run_id / "run.db"
    # Explicit Path → use that path (backward-compat override via AUTOFIX_OBSERVABILITY_DB)
    sqlite_db_path: Path | None = None


def resolve_observability_config(*, repo_root: Path, metadata: dict[str, Any]) -> ObservabilityConfig:
    resolved_results_dir = _resolve_path(
        metadata_value=metadata.get("results_dir"),
        env_value=os.environ.get("AUTOFIX_RESULTS_DIR"),
        default=repo_root / "results",
        repo_root=repo_root,
    )
    # Only set an explicit sqlite_db_path when a caller has overridden it.
    # When None, observer_factory will default to results_dir / run_id / "run.db".
    sqlite_db_path = _resolve_optional_path(
        metadata_value=metadata.get("observability_db"),
        env_value=os.environ.get("AUTOFIX_OBSERVABILITY_DB"),
        repo_root=repo_root,
    )

    return ObservabilityConfig(
        enabled=_resolve_bool(
            metadata_value=metadata.get("observability_enabled"),
            env_value=os.environ.get("AUTOFIX_OBSERVABILITY_ENABLED"),
            default=True,
        ),
        interactive=_resolve_bool(
            metadata_value=metadata.get("interactive"),
            env_value=os.environ.get("AUTOFIX_INTERACTIVE"),
            default=False,
        ),
        results_dir=resolved_results_dir,
        sqlite_db_path=sqlite_db_path,
        live_log_enabled=_resolve_bool(
            metadata_value=metadata.get("live_log_enabled"),
            env_value=os.environ.get("AUTOFIX_LIVE_LOG"),
            default=True,
        ),
    )


def _resolve_bool(*, metadata_value: Any, env_value: str | None, default: bool) -> bool:
    if isinstance(metadata_value, bool):
        return metadata_value
    if isinstance(metadata_value, str):
        lowered = metadata_value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False

    if env_value is not None:
        lowered = env_value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False

    return default


def _resolve_path(*, metadata_value: Any, env_value: str | None, default: Path, repo_root: Path) -> Path:
    raw = metadata_value if isinstance(metadata_value, str) else env_value
    if raw is None:
        return default
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate


def _resolve_optional_path(*, metadata_value: Any, env_value: str | None, repo_root: Path) -> Path | None:
    """Like _resolve_path but returns None when no explicit value is set."""
    raw = metadata_value if isinstance(metadata_value, str) else env_value
    if raw is None:
        return None
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate
