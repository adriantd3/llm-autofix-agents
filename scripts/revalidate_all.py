#!/usr/bin/env python3
"""
revalidate_all.py — Re-validación completa de todos los runs APR del experimento.

Re-ejecuta la validación formal desde cero para TODOS los runs resueltos,
usando el skill apr-validator correctamente (Copilot/Claude como juez, sin LLM externo).

Los batches de QuixBugs se agrupan por arquitectura+modelo (igual que en
run_final_experiment.py) para reducir el número de invocaciones Copilot.

Uso
───────────────────────────────────────────────────────────────────────────────
  export NTFY_TOPIC=tfm-adriantd       # opcional — notificaciones ntfy
  uv run python scripts/revalidate_all.py

  # Ver el plan sin ejecutar nada:
  uv run python scripts/revalidate_all.py --dry-run

  # Reanudar desde un grupo específico (filtra por nombre del batch dir):
  uv run python scripts/revalidate_all.py --from quixbugs-mono-agent-gemma

  # Validar en paralelo con hasta N procesos copilot simultáneos (default: 5):
  uv run python scripts/revalidate_all.py --parallel 3

  # Segundos de espera entre grupos para no saturar la API:
  uv run python scripts/revalidate_all.py --wait 60
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Paths & config
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results"

COPILOT_MODEL = "claude-sonnet-4.5"
COPILOT_TIMEOUT_SECS = 900  # 15 min max per validation group

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ascii_header(value: str) -> str:
    """Return an ASCII-safe header value for httpx."""
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii")


def notify(
    title: str,
    message: str,
    *,
    priority: int = 3,
    tags: tuple[str, ...] | list[str] = (),
    _http_post=httpx.post,
) -> None:
    """Send an ntfy push notification. Never raises."""
    topic = os.environ.get("NTFY_TOPIC", "")
    if not topic:
        print(f"[ntfy] (no topic) {title}: {message}")
        return
    try:
        headers: dict[str, str] = {
            "Title": _ascii_header(title),
            "Priority": str(priority),
        }
        if tags:
            headers["Tags"] = ",".join(tags)
        _http_post(
            f"https://ntfy.sh/{topic}",
            content=message.encode("utf-8"),
            headers=headers,
            timeout=10,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[ntfy] WARNING: notificación no enviada ({exc})")


# ---------------------------------------------------------------------------
# Batch discovery & grouping
# ---------------------------------------------------------------------------


def collect_batch_dirs(results_dir: Path) -> list[Path]:
    """Return all batch-experiment-* dirs that contain a batch.db."""
    return sorted(
        p for p in results_dir.glob("batch-experiment-*")
        if (p / "batch.db").exists()
    )


def _validation_group_key(batch_dir: Path) -> str:
    """Group key for validation.

    QuixBugs per-bug dirs share a key so all bugs for the same arch+model
    are validated together in one Copilot call. BugsInPy dirs are their own key.
    """
    name = batch_dir.name
    if "quixbugs" not in name:
        return name
    # Strip timestamp suffix (-YYYYMMDDTHHMMSSZ)
    base = re.sub(r"-\d{8}T\d{6}Z$", "", name)
    # Strip the last '-{bug_name}' segment
    return base.rsplit("-", 1)[0]


def group_batch_dirs(batch_dirs: list[Path]) -> list[list[Path]]:
    """Group batch dirs so QuixBugs per-bug dirs are validated together."""
    groups: dict[str, list[Path]] = {}
    for bd in sorted(batch_dirs):
        key = _validation_group_key(bd)
        groups.setdefault(key, []).append(bd)
    return list(groups.values())


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def build_validation_prompt(batch_dirs: list[Path]) -> str:
    if len(batch_dirs) == 1:
        dirs_block = str(batch_dirs[0])
    else:
        dirs_block = "\n".join(f"  - {d}" for d in sorted(batch_dirs))
    label = "directory" if len(batch_dirs) == 1 else "directories"
    return (
        f"Use the apr-validator skill to formally re-validate all APR runs in the following batch {label}.\n\n"
        f"Batch {label}:\n{dirs_block}\n\n"
        f"Repository root: {REPO_ROOT}\n\n"
        "This is a full re-validation from scratch. Follow the two-step workflow from Step 7 of the apr-validator skill:\n"
        "1. Call validate_batch.py --list-runs --force on each batch.db to get ALL resolved runs (including already-validated ones).\n"
        "2. For each run, apply the 6-step validation protocol to produce a verdict.\n"
        "3. Pipe the full verdicts JSON array to validate_batch.py (write mode) to persist.\n"
        "IMPORTANT: Use --force with --list-runs so that already-validated runs are included and overwritten.\n"
        "If validate_batch.py fails for any reason, immediately use the fallback section in apr-validator SKILL.md: read the DB with sqlite3, resolve /results paths to the host repo, and write verdicts directly with DELETE + INSERT so each run_id ends with exactly one row.\n"
        "The script is a pure persistence layer — you are the judge, not the script."
    )


def run_validation_group(batch_dirs: list[Path], *, dry_run: bool = False) -> tuple[bool, str | None]:
    """Invoke copilot CLI to re-validate all runs in *batch_dirs*.

    Returns (ok, reason).
    reason values on failure: oauth | timeout | exit:<code> | exception:<msg>
    """
    prompt = build_validation_prompt(batch_dirs)
    label = (
        batch_dirs[0].name if len(batch_dirs) == 1
        else f"{batch_dirs[0].name} (+{len(batch_dirs) - 1} más)"
    )
    cmd = [
        "copilot",
        "-p", prompt,
        "--allow-all",
        "--no-ask-user",
        f"--model={COPILOT_MODEL}",
    ]

    print(f"[validación] {utcnow()} — {label}")
    if dry_run:
        print(f"  [dry-run] copilot -p '<prompt>' --allow-all --model={COPILOT_MODEL}")
        return True, None

    try:
        result = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            timeout=COPILOT_TIMEOUT_SECS,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            combined = (result.stdout or "") + "\n" + (result.stderr or "")
            reason = "oauth" if "No authentication information found" in combined else f"exit:{result.returncode}"
            print(f"  [validación] FALLO — exit {result.returncode}", file=sys.stderr)
            return False, reason
        return True, None
    except subprocess.TimeoutExpired:
        print(f"  [validación] TIMEOUT ({COPILOT_TIMEOUT_SECS}s) — {label}", file=sys.stderr)
        return False, "timeout"
    except Exception as exc:  # noqa: BLE001
        print(f"  [validación] EXCEPCIÓN — {label}: {exc}", file=sys.stderr)
        return False, f"exception:{exc}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Mostrar el plan completo sin ejecutar nada.",
    )
    parser.add_argument(
        "--from", dest="start_from", metavar="NAME",
        help="Saltar hasta el primer grupo cuyo nombre de directorio contiene NAME.",
    )
    parser.add_argument(
        "--parallel", type=int, default=5, metavar="N",
        help="Número máximo de invocaciones copilot en paralelo (default: 5).",
    )
    parser.add_argument(
        "--wait", type=int, default=0, metavar="SECS",
        help="Segundos de espera entre grupos (default: 0, útil para evitar rate-limit).",
    )
    args = parser.parse_args()

    batch_dirs = collect_batch_dirs(RESULTS_DIR)
    if not batch_dirs:
        print(f"ERROR: No se encontraron batch-experiment-* con batch.db en {RESULTS_DIR}")
        return 1

    groups = group_batch_dirs(batch_dirs)

    # --from: skip groups until first match
    if args.start_from:
        idx = next(
            (i for i, g in enumerate(groups) if args.start_from in g[0].name),
            None,
        )
        if idx is None:
            print(f"ERROR: Ningún grupo contiene '{args.start_from}' en el nombre del primer directorio.")
            print("Grupos disponibles:")
            for g in groups:
                print(f"  {g[0].name}" + (f" (+{len(g)-1} más)" if len(g) > 1 else ""))
            return 1
        groups = groups[idx:]

    total_dirs = sum(len(g) for g in groups)
    print("=" * 64)
    print(f"  Re-validación APR — {utcnow()}")
    print(f"  Batch dirs : {total_dirs}  →  grupos : {len(groups)}")
    print(f"  Paralelo   : {args.parallel}  |  wait  : {args.wait}s")
    print(f"  Modelo     : {COPILOT_MODEL}")
    print("=" * 64)

    for g in groups:
        if len(g) == 1:
            print(f"  grupo : {g[0].name}")
        else:
            print(f"  grupo : {g[0].name} (+{len(g)-1} más, ej: {g[-1].name})")

    if args.dry_run:
        print(f"\n[dry-run] {len(groups)} invocaciones copilot previstas (máx {args.parallel} en paralelo).")
        return 0

    notify(
        "TFM Re-validación iniciada",
        f"{total_dirs} batch dirs → {len(groups)} grupos — {utcnow()}",
        priority=3,
        tags=("arrows_counterclockwise", "hourglass_flowing_sand"),
    )

    failed_groups: list[str] = []
    completed = 0
    oauth_stop = False

    import time

    for chunk_start in range(0, len(groups), args.parallel):
        chunk = groups[chunk_start:chunk_start + args.parallel]
        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            futures = {
                executor.submit(run_validation_group, group, dry_run=args.dry_run): group
                for group in chunk
            }

            for future in as_completed(futures):
                group = futures[future]
                ok, reason = future.result()
                completed += 1
                label = (
                    group[0].name if len(group) == 1
                    else f"{group[0].name} (+{len(group)-1} más)"
                )
                status = "OK" if ok else "FALLO"
                print(f"  [{completed}/{len(groups)}] {status} — {label}")
                if not ok:
                    failed_groups.append(label)

                # Notify every 5 completed groups, plus immediate alerts on failures.
                if (completed % 5 == 0) or (not ok):
                    detail = f"{status} — {label}"
                    if reason:
                        detail = f"{detail} | reason={reason}"
                    notify(
                        f"TFM Re-validación: {completed}/{len(groups)} grupos",
                        detail,
                        priority=3 if ok else 5,
                        tags=("heavy_check_mark",) if ok else ("warning",),
                    )

                if reason == "oauth":
                    oauth_stop = True
                    notify(
                        "TFM Re-validación detenida por OAuth",
                        f"Fallo de autenticación Copilot detectado en {label}. Se detiene la ejecución.",
                        priority=5,
                        tags=("no_entry", "warning"),
                    )
                    break

        if oauth_stop:
            break

        # Wait between blocks of N groups if requested.
        if args.wait > 0 and (chunk_start + args.parallel) < len(groups):
            print(f"[pausa] Esperando {args.wait}s antes del siguiente bloque...")
            time.sleep(args.wait)

    ok_count = len(groups) - len(failed_groups)
    print()
    print("=" * 64)
    print(f"  Re-validación finalizada: {ok_count}/{len(groups)} grupos OK")
    if oauth_stop:
        print("  Ejecución detenida por error de autenticación OAuth")
    if failed_groups:
        print(f"  Fallidos ({len(failed_groups)}):")
        for name in failed_groups:
            print(f"    x {name}")
    print("=" * 64)

    notify(
        f"TFM Re-validación completada: {ok_count}/{len(groups)} OK",
        (
            f"{len(failed_groups)} fallidos — {utcnow()}"
            if not oauth_stop else
            f"{len(failed_groups)} fallidos (detenido por OAuth) — {utcnow()}"
        ),
        priority=4 if (not failed_groups and not oauth_stop) else 5,
        tags=("partying_face",) if not failed_groups else ("triangular_flag_on_post",),
    )

    return 0 if (not failed_groups and not oauth_stop) else 1


if __name__ == "__main__":
    sys.exit(main())
