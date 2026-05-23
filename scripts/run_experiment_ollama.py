#!/usr/bin/env python3
"""
run_experiment_ollama.py

Runs all Ollama experiment batches (excludes gpt-5.4) sequentially, split by
project, with VRAM-aware GPU scheduling between sub-batches.

Sub-batch splitting
  Each big YAML (all projects combined) is split into one temp YAML per project.
  Results dirs are named  batch-{name}-{project}-{timestamp}/  so the skip
  logic is per project, not per full batch.

GPU scheduling
  Before starting each sub-batch, the script queries free VRAM via nvidia-smi
  and currently loaded Ollama model sizes.  It then selects the *heaviest*
  model whose batch fits in available VRAM, prioritising gemma4-26b-ctx32k over
  qwen3.5-9b-ctx65k.  If neither model fits the script sleeps --gpu-poll seconds
  (default 300) and retries.  This runs indefinitely — design intent is to
  leave the script running for days on a shared GPU host.
  When nvidia-smi is unavailable (e.g. NVML version mismatch), the script
  falls back to sequential execution and logs a warning.

Completion detection
  A sub-batch is considered complete only when results/batch-{name}/ contains
  batch.db — the file the framework writes after all bugs have run.  A results
  dir without batch.db means the run was interrupted and will be re-executed.

Resilience options
  --force       Re-run even if batch.db exists for that sub-batch.
  --from NAME   Skip all sub-batches before the first one whose name contains
                NAME  (useful when resuming after a crash mid-sequence).
  --dry-run     Print the execution plan without running anything.

Long-running usage (recommended — keeps the process alive after SSH disconnect)
  tmux new -s exp
  uv run python scripts/run_experiment_ollama.py 2>&1 | tee results/run-$(date -u +%%Y%%m%%dT%%H%%M%%SZ).log
  # Reconnect later:
  tmux attach -t exp
  # Or just tail the log:
  tail -f results/run-*.log
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from llm_autofix_agents.experiment.scheduler import (
    DEFAULT_MODEL_VRAM_MIB,
    OLLAMA_DEFAULT_HOST,
    SubBatch,
    get_free_vram_mib,
    get_ollama_loaded_vram_mib,
    get_ollama_model_sizes_mib,
    select_next_batch,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
BATCHES_DIR = REPO_ROOT / "batches" / "experiment"
RESULTS_DIR = REPO_ROOT / "results"
LOCK_FILE = REPO_ROOT / ".experiment.lock"
OLLAMA_HOST = OLLAMA_DEFAULT_HOST


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def discover_configs(batches_dir: Path) -> list[Path]:
    """All YAMLs in batches_dir excluding gpt-5.4, sorted by model name.

    Sorting by model as primary key means all gemma4 sub-batches run before
    all qwen3.5 sub-batches — Ollama loads each model only once.
    """
    configs = [p for p in batches_dir.glob("*.yaml") if "gpt-5.4" not in p.name]

    def model_key(p: Path) -> tuple[str, str]:
        parts = p.stem.split("-")
        model = "-".join(parts[-2:]) if len(parts) >= 2 else p.stem
        return (model, p.name)

    return sorted(configs, key=model_key)


def split_by_project(config_path: Path, tmp_dir: Path) -> list[Path]:
    """Split a batch YAML into one temp YAML per project.

    Bug IDs follow the pattern  {project}-{number}  (e.g. thefuck-1,
    youtube-dl-2).  Bugs are grouped by the project prefix (everything before
    the last dash+number).

    The dataset path is resolved to absolute so the temp YAML works regardless
    of where it is placed.
    """
    data = yaml.safe_load(config_path.read_text())
    bugs: list[str] = data.get("bugs", [])

    # Group by project: 'thefuck-1' -> 'thefuck', 'youtube-dl-2' -> 'youtube-dl'
    by_project: dict[str, list[str]] = {}
    for bug in bugs:
        project = bug.rsplit("-", 1)[0]
        by_project.setdefault(project, []).append(bug)

    # Resolve dataset ref to absolute path (temp YAML lives in a different dir)
    dataset_ref = data.get("dataset", "")
    if dataset_ref and not Path(dataset_ref).is_absolute():
        dataset_ref = str((config_path.parent / dataset_ref).resolve())

    paths: list[Path] = []
    for project in sorted(by_project.keys()):
        per_project_name = f"{data['name']}-{project}"
        per_project_data = {
            **data,
            "name": per_project_name,
            "description": f"{data.get('description', '')} [{project}]",
            "dataset": dataset_ref,
            "bugs": by_project[project],
        }
        tmp_path = tmp_dir / f"{config_path.stem}-{project}.yaml"
        tmp_path.write_text(
            yaml.dump(
                per_project_data,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )
        )
        paths.append(tmp_path)

    return paths


# ---------------------------------------------------------------------------
# Completion detection
# ---------------------------------------------------------------------------


def find_completed_batch(name: str, results_dir: Path) -> Path | None:
    """Return the first results dir for *name* that contains batch.db.

    A dir without batch.db was interrupted mid-run and is NOT considered done.
    """
    for candidate in sorted(results_dir.glob(f"batch-{name}-*")):
        if (candidate / "batch.db").exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Lockfile
# ---------------------------------------------------------------------------


class AlreadyRunningError(RuntimeError):
    pass


def acquire_lock(lock_path: Path) -> None:
    """Write a PID lockfile.  Raises AlreadyRunningError if another instance
    is running.  Stale locks (dead PID) are silently overwritten."""
    if lock_path.exists():
        try:
            pid = int(lock_path.read_text().strip())
            os.kill(pid, 0)  # signal 0: check if process exists
            raise AlreadyRunningError(
                f"Another instance is already running (PID {pid}). "
                f"If that process is dead, remove {lock_path} manually."
            )
        except (ValueError, ProcessLookupError, PermissionError):
            pass  # stale lock -- overwrite
    lock_path.write_text(str(os.getpid()) + "\n")


def release_lock(lock_path: Path) -> None:
    lock_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run sub-batches even if batch.db already exists.",
    )
    parser.add_argument(
        "--from",
        dest="start_from",
        metavar="NAME",
        help="Skip all sub-batches before the first whose name contains NAME.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the execution plan without running anything.",
    )
    parser.add_argument(
        "--gpu-poll",
        type=int,
        default=300,
        metavar="SECS",
        help="Seconds to sleep when GPU VRAM is too low (default: 300).",
    )
    args = parser.parse_args()

    if not args.dry_run:
        try:
            acquire_lock(LOCK_FILE)
        except AlreadyRunningError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    try:
        return _run(args)
    finally:
        if not args.dry_run:
            release_lock(LOCK_FILE)


def _run(args: argparse.Namespace) -> int:
    configs = discover_configs(BATCHES_DIR)
    if not configs:
        print(f"ERROR: No configs found in {BATCHES_DIR} (excluding gpt-5.4)")
        return 1

    # Build the VRAM table used for scheduling.
    # Strategy: start with live Ollama sizes (file size = weights only) as a
    # baseline for any model not in DEFAULT_MODEL_VRAM_MIB, then overlay the
    # calibrated DEFAULT values (weights + KV cache at configured num_ctx).
    # This ensures known models always use accurate measured VRAM, while any
    # newly added model not yet in DEFAULT falls back to a live file-size estimate.
    live_sizes = get_ollama_model_sizes_mib(OLLAMA_HOST)
    model_vram = {**live_sizes, **DEFAULT_MODEL_VRAM_MIB}

    with tempfile.TemporaryDirectory(prefix="exp_subbatches_") as tmp_str:
        tmp_dir = Path(tmp_str)

        # Split every config by project -> flat list of sub-batch temp YAMLs
        all_subs: list[Path] = []
        for cfg in configs:
            all_subs.extend(split_by_project(cfg, tmp_dir))

        # --from: find cut point
        if args.start_from:
            idx = next(
                (i for i, p in enumerate(all_subs) if args.start_from in p.stem),
                None,
            )
            if idx is None:
                print(f"ERROR: No sub-batch matching '{args.start_from}'.")
                print("Available sub-batches:")
                for p in all_subs:
                    print(f"  {p.stem}")
                return 1
            all_subs = all_subs[idx:]

        # Build SubBatch list with completion detection
        sub_batches: list[SubBatch] = []
        for sub in all_subs:
            sub_data = yaml.safe_load(sub.read_text())
            name: str = sub_data.get("name") or sub.stem
            model: str = (
                sub_data.get("global", {}).get("llm", {}).get("model") or "unknown"
            )
            skip_reason: str | None = None
            if not args.force:
                existing = find_completed_batch(name, RESULTS_DIR)
                if existing:
                    skip_reason = f"done -> {existing.name}"
            sub_batches.append(
                SubBatch(path=sub, name=name, model=model, skip_reason=skip_reason)
            )

        to_run = sum(1 for b in sub_batches if b.skip_reason is None)
        to_skip = len(sub_batches) - to_run

        print("=" * 64)
        print(f"  Ollama experiment run -- {utcnow()}")
        print(
            f"  Sub-batches : {len(sub_batches)}  |  "
            f"Run : {to_run}  |  Skip : {to_skip}"
        )
        print(f"  GPU poll interval : {args.gpu_poll}s")
        print(f"  Model VRAM estimates (MiB): {model_vram}")
        print("=" * 64)
        print()
        print("Execution plan (heaviest model prioritised when VRAM permits):")
        for b in sub_batches:
            tag = f"SKIP ({b.skip_reason})" if b.skip_reason else "RUN"
            print(f"  [{tag:<42}] {b.name}  [{b.model}]")
        print()

        if args.dry_run:
            print("--dry-run: nothing executed.")
            return 0

        # Print skips up front, then work through the pending queue
        for b in sub_batches:
            if b.skip_reason:
                print(f"SKIP {b.name}  ({b.skip_reason})")

        pending = [b for b in sub_batches if b.skip_reason is None]
        passed: list[str] = []
        failed: list[str] = []
        total_to_run = len(pending)
        completed = 0

        while pending:
            free_vram = get_free_vram_mib()
            ollama_vram = get_ollama_loaded_vram_mib(OLLAMA_HOST)

            next_batch = select_next_batch(
                pending, free_vram, ollama_vram, model_vram
            )

            if next_batch is None:
                vram_info = (
                    f"free: {free_vram} MiB, Ollama: {ollama_vram} MiB"
                    if free_vram is not None
                    else "VRAM unknown"
                )
                print(
                    f"[GPU] {utcnow()} -- No model fits ({vram_info}). "
                    f"Sleeping {args.gpu_poll}s..."
                )
                time.sleep(args.gpu_poll)
                continue

            pending.remove(next_batch)
            completed += 1

            vram_line = (
                f"  Free VRAM : {free_vram} MiB  |  "
                f"Ollama loaded : {ollama_vram} MiB"
                if free_vram is not None
                else "  Free VRAM : unknown (nvidia-smi unavailable)"
            )
            print()
            print("-" * 64)
            print(f"[{completed}/{total_to_run}] Running : {next_batch.name}")
            print(f"  Model   : {next_batch.model}")
            print(vram_line)
            print(f"  Start   : {utcnow()}")
            print("-" * 64)

            result = subprocess.run(
                ["uv", "run", "autofix", "batch", str(next_batch.path)],
                cwd=REPO_ROOT,
            )

            if result.returncode == 0:
                passed.append(next_batch.name)
                print(f"  Done    : {utcnow()}")
            else:
                failed.append(next_batch.name)
                print(
                    f"  FAILED  : {next_batch.name} (exit {result.returncode})"
                    f" -- {utcnow()}",
                    file=sys.stderr,
                )

        print()
        print("=" * 64)
        print(f"  Summary -- {utcnow()}")
        print("=" * 64)
        print(f"Passed ({len(passed)}):")
        for p in passed:
            print(f"  v {p}")
        print(f"Failed ({len(failed)}):")
        for f in failed:
            print(f"  x {f}")
        print()
        print("To aggregate results:")
        print(
            "  make aggregate OUT=results/experiment.db"
            " BATCH_DIRS='results/batch-experiment-*'"
        )
        return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
