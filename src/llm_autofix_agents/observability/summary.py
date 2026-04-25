from __future__ import annotations

import json
from pathlib import Path


def write_summary(
    *,
    summary_path: Path,
    run_id: str,
    status: str,
    stop_reason: str,
    duration_seconds: float,
    iterations: int,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    changed_files_count: int,
    observability_db: str,
    live_log: str | None,
) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "status": status,
        "stop_reason": stop_reason,
        "duration_seconds": duration_seconds,
        "iterations": iterations,
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "total": total_tokens,
        },
        "changed_files_count": changed_files_count,
        "observability_db": observability_db,
        "live_log": live_log,
    }
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
