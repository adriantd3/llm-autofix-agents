#!/usr/bin/env python3
"""
run_final_experiment.py — Script definitivo de experimento + validación TFM.

Diseñado para ejecutarse en **dos procesos independientes** en paralelo:

  Proceso A (Ollama — por defecto)
  ─────────────────────────────────────────────────────────────────────────────
  export NTFY_TOPIC=tfm-adriantd-ollama
  tmux new -s ollama
  uv run python scripts/run_final_experiment.py 2>&1 | tee results/run-ollama-$(date -u +%Y%m%dT%H%M%SZ).log
  # Reconectar:  tmux attach -t ollama
  # Solo log:    tail -f results/run-ollama-*.log

  Proceso B (GPT — flag --gpt-only)
  ─────────────────────────────────────────────────────────────────────────────
  export NTFY_TOPIC_GPT=tfm-adriantd-gpt
  export OPENAI_API_KEY=sk-...
  tmux new -s gpt
  uv run python scripts/run_final_experiment.py --gpt-only 2>&1 | tee results/run-gpt-$(date -u +%Y%m%dT%H%M%SZ).log

Fases
─────────────────────────────────────────────────────────────────────────────
1. Validación de entorno (falla rápido si faltan variables)
2. Ejecución de batches con VRAM scheduling (Ollama) o secuencial (GPT)
3. Balance check de OpenAI entre batches en modo GPT
4. Validación formal con copilot CLI — una llamada por batch dir producido
5. Notificaciones ntfy a lo largo de todo el proceso

Flags de control
─────────────────────────────────────────────────────────────────────────────
  --gpt-only              Solo batches gpt-5.4-mini; usa NTFY_TOPIC_GPT
  --force                 Re-ejecutar aunque exista batch.db
  --from NAME             Saltar hasta el primer sub-batch cuyo nombre contiene NAME
  --dry-run               Muestra el plan completo sin ejecutar nada
  --gpu-poll SECS         Segundos de espera cuando la VRAM no es suficiente (default: 300)
  --skip-validation       Omitir la fase de validación copilot
  --validation-only       Solo validar — no ejecutar experimentos.
                          Escanea TODOS los batch-experiment-* existentes en results/
  --validation-wait SECS  Segundos entre invocaciones copilot (default: 300)
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn

import httpx
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
LOCK_FILE_OLLAMA = REPO_ROOT / ".experiment.lock"
LOCK_FILE_GPT = REPO_ROOT / ".experiment-gpt.lock"
OLLAMA_HOST = OLLAMA_DEFAULT_HOST

# ---------------------------------------------------------------------------
# Copilot configuration
# ---------------------------------------------------------------------------

# Verify the exact model name with:  copilot --help | grep -A5 'model'
# Available models depend on your Copilot subscription.
COPILOT_MODEL = "claude-sonnet-4-6"
COPILOT_EFFORT = "medium"
COPILOT_TIMEOUT_SECS = 900  # 15 min max per validation batch

# ---------------------------------------------------------------------------
# OpenAI balance check
# ---------------------------------------------------------------------------

# Minimum remaining credits (USD) before stopping GPT runs.
# Set to 0 to disable balance enforcement (pay-as-you-go accounts).
OPENAI_MIN_BALANCE_USD = 1.0
OPENAI_CREDIT_GRANTS_URL = "https://api.openai.com/v1/organization/credit_grants"

# ---------------------------------------------------------------------------
# Required environment variables per mode
# ---------------------------------------------------------------------------

_REQUIRED_OLLAMA = ["NTFY_TOPIC"]
_REQUIRED_GPT = ["NTFY_TOPIC_GPT", "OPENAI_API_KEY"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_env(gpt_only: bool, dry_run: bool = False) -> None:  # noqa: FBT001,FBT002
    """Fail fast if required environment variables are missing.

    Called before any other work so the user knows immediately what to fix,
    even in --dry-run mode.
    """
    required = _REQUIRED_GPT if gpt_only else _REQUIRED_OLLAMA
    missing = [var for var in required if not os.environ.get(var, "").strip()]
    if not missing:
        return

    lines = [f"  - {var}  →  export {var}=<value>" for var in missing]
    mode = "GPT (--gpt-only)" if gpt_only else "Ollama"
    print(
        f"\nERROR: Variables de entorno requeridas para el modo {mode} no configuradas:\n"
        + "\n".join(lines)
        + "\n\nEl script no puede continuar."
        + (
            "\n\n[--dry-run] La validación de entorno se aplica también en dry-run."
            if dry_run
            else ""
        ),
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# ntfy notifications
# ---------------------------------------------------------------------------


def notify(
    title: str,
    message: str,
    *,
    priority: int = 3,
    tags: tuple[str, ...] | list[str] = (),
    topic: str = "",
    _http_post=httpx.post,  # injectable for tests
) -> None:
    """Send an ntfy push notification.  Never raises — failures are logged only.

    Tags are ntfy emoji short codes (e.g. "warning" → ⚠️, "rocket" → 🚀).
    Full list: https://docs.ntfy.sh/emojis/
    """
    resolved_topic = topic or os.environ.get("NTFY_TOPIC", "")
    if not resolved_topic:
        print(f"[ntfy] (no topic) {title}: {message}")
        return
    try:
        headers: dict[str, str] = {
            "Title": title,
            "Priority": str(priority),
        }
        if tags:
            headers["Tags"] = ",".join(tags)
        _http_post(
            f"https://ntfy.sh/{resolved_topic}",
            content=message.encode(),
            headers=headers,
            timeout=10,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[ntfy] WARNING: notificación no enviada ({exc})")


# ---------------------------------------------------------------------------
# OpenAI balance check
# ---------------------------------------------------------------------------


def check_openai_balance(
    api_key: str,
    min_balance_usd: float = OPENAI_MIN_BALANCE_USD,
    _http_get=httpx.get,  # injectable for tests
) -> tuple[bool, float | None]:
    """Check remaining OpenAI credits.

    Returns (can_continue, remaining_usd).
    - (True, None)  → endpoint unavailable or pay-as-you-go (proceed with warning)
    - (True, X)     → X >= min_balance_usd (proceed)
    - (False, X)    → X < min_balance_usd (stop)
    """
    try:
        resp = _http_get(
            OPENAI_CREDIT_GRANTS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code == 404:
            print("[balance] Endpoint de créditos no disponible (cuenta pay-as-you-go). Continuando.")
            return True, None
        resp.raise_for_status()
        data = resp.json()
        remaining: float = float(data.get("total_available", min_balance_usd))
        if remaining < min_balance_usd:
            return False, remaining
        return True, remaining
    except Exception as exc:  # noqa: BLE001
        print(f"[balance] WARNING: no se pudo verificar el saldo de OpenAI ({exc}). Continuando.")
        return True, None


# ---------------------------------------------------------------------------
# Batch discovery
# ---------------------------------------------------------------------------


def discover_configs(batches_dir: Path, *, gpt_only: bool) -> list[Path]:
    """Return sorted list of experiment YAMLs for the selected mode.

    Ollama: all YAMLs excluding gpt-5.4, sorted by model name (loads model once).
    GPT:    only YAMLs containing gpt-5.4, sorted by name.
    """
    if gpt_only:
        configs = sorted(p for p in batches_dir.glob("*.yaml") if "gpt-5.4" in p.name)
    else:
        configs = [p for p in batches_dir.glob("*.yaml") if "gpt-5.4" not in p.name]

        def _model_key(p: Path) -> tuple[str, str]:
            parts = p.stem.split("-")
            model = "-".join(parts[-2:]) if len(parts) >= 2 else p.stem
            return (model, p.name)

        configs = sorted(configs, key=_model_key)
    return configs


def split_by_project(config_path: Path, tmp_dir: Path) -> list[Path]:
    """Split a batch YAML into one temp YAML per project.

    Bug IDs follow the pattern {project}-{number} (e.g. thefuck-1).
    The dataset path is resolved to absolute so temp YAMLs work from any cwd.
    """
    data = yaml.safe_load(config_path.read_text())
    bugs: list[str] = data.get("bugs", [])

    by_project: dict[str, list[str]] = {}
    for bug in bugs:
        project = bug.rsplit("-", 1)[0]
        by_project.setdefault(project, []).append(bug)

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
            yaml.dump(per_project_data, default_flow_style=False, sort_keys=False, allow_unicode=True)
        )
        paths.append(tmp_path)
    return paths


# ---------------------------------------------------------------------------
# Completion detection
# ---------------------------------------------------------------------------


def find_completed_batch(name: str, results_dir: Path) -> Path | None:
    """Return the first results dir for *name* that contains batch.db."""
    for candidate in sorted(results_dir.glob(f"batch-{name}-*")):
        if (candidate / "batch.db").exists():
            return candidate
    return None


def find_produced_batch_dir(name: str, results_dir: Path, after_mtime: float) -> Path | None:
    """Return the most recent results dir for *name* created after *after_mtime*."""
    candidates = [
        p for p in sorted(results_dir.glob(f"batch-{name}-*"))
        if p.stat().st_mtime > after_mtime
    ]
    return candidates[-1] if candidates else None


# ---------------------------------------------------------------------------
# Lock file
# ---------------------------------------------------------------------------


class AlreadyRunningError(RuntimeError):
    pass


def acquire_lock(lock_path: Path) -> None:
    if lock_path.exists():
        try:
            pid = int(lock_path.read_text().strip())
            os.kill(pid, 0)
            raise AlreadyRunningError(
                f"Otra instancia ya está corriendo (PID {pid}). "
                f"Si ese proceso ya no existe, elimina {lock_path} manualmente."
            )
        except (ValueError, ProcessLookupError, PermissionError):
            pass
    lock_path.write_text(str(os.getpid()) + "\n")


def release_lock(lock_path: Path) -> None:
    lock_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Validation phase
# ---------------------------------------------------------------------------


def build_validation_prompt(batch_dir: Path) -> str:
    return (
        "Use the apr-validator skill to formally validate all APR runs in this batch.\n\n"
        f"Batch directory: {batch_dir}\n"
        f"Repository root: {REPO_ROOT}\n\n"
        "For each run-* subdirectory found in the batch directory, follow the 6-step\n"
        "validation protocol defined in the apr-validator skill and record the verdict\n"
        "in the batch database (batch.db)."
    )


def run_validation(
    batch_dir: Path,
    *,
    dry_run: bool = False,
    ntfy_topic: str = "",
) -> bool:
    """Invoke copilot CLI to validate all runs in *batch_dir*.

    Returns True on success (exit code 0), False otherwise.
    """
    prompt = build_validation_prompt(batch_dir)
    cmd = [
        "copilot",
        "-p", prompt,
        "--allow-all",
        "--no-ask-user",
        f"--model={COPILOT_MODEL}",
        f"--effort={COPILOT_EFFORT}",
    ]

    print(f"[validación] {utcnow()} — {batch_dir.name}")
    if dry_run:
        print(f"  [dry-run] copilot -p '<prompt>' --allow-all --model={COPILOT_MODEL} --effort={COPILOT_EFFORT}")
        return True

    try:
        result = subprocess.run(cmd, cwd=str(REPO_ROOT), timeout=COPILOT_TIMEOUT_SECS)
        if result.returncode != 0:
            print(f"  [validación] FALLO — exit {result.returncode}", file=sys.stderr)
            notify(
                f"TFM: Error validacion {batch_dir.name}",
                f"copilot salió con código {result.returncode}",
                priority=5,
                tags=("skull", "warning"),
                topic=ntfy_topic,
            )
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"  [validación] TIMEOUT ({COPILOT_TIMEOUT_SECS}s) — {batch_dir.name}", file=sys.stderr)
        notify(
            f"TFM: Timeout validacion {batch_dir.name}",
            f"Superado el límite de {COPILOT_TIMEOUT_SECS}s",
            priority=5,
            tags=("skull", "warning"),
            topic=ntfy_topic,
        )
        return False


def collect_all_experiment_batch_dirs(results_dir: Path) -> list[Path]:
    """Return all batch-experiment-* dirs in results_dir that contain batch.db."""
    return sorted(
        p for p in results_dir.glob("batch-experiment-*")
        if (p / "batch.db").exists()
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--gpt-only", action="store_true", help="Solo batches gpt-5.4-mini.")
    parser.add_argument("--force", action="store_true", help="Re-ejecutar aunque exista batch.db.")
    parser.add_argument("--from", dest="start_from", metavar="NAME",
                        help="Saltar hasta el primer sub-batch cuyo nombre contiene NAME.")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar plan sin ejecutar nada.")
    parser.add_argument("--gpu-poll", type=int, default=300, metavar="SECS",
                        help="Segundos de espera con VRAM insuficiente (default: 300).")
    parser.add_argument("--skip-validation", action="store_true",
                        help="Omitir la fase de validación copilot.")
    parser.add_argument("--validation-only", action="store_true",
                        help="Solo validar — escanea todos los batch-experiment-* existentes.")
    parser.add_argument("--validation-wait", type=int, default=300, metavar="SECS",
                        help="Segundos entre invocaciones copilot (default: 300).")
    args = parser.parse_args()

    validate_env(args.gpt_only, dry_run=args.dry_run)

    ntfy_topic = (
        os.environ.get("NTFY_TOPIC_GPT", "") if args.gpt_only
        else os.environ.get("NTFY_TOPIC", "")
    )
    mode_label = "GPT" if args.gpt_only else "Ollama"
    lock_path = LOCK_FILE_GPT if args.gpt_only else LOCK_FILE_OLLAMA

    if not args.dry_run:
        try:
            acquire_lock(lock_path)
        except AlreadyRunningError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    # Install signal handler for graceful shutdown
    def _handle_signal(signum: int, frame: object) -> NoReturn:
        print(f"\n[signal] Señal {signum} recibida — limpiando y saliendo...")
        release_lock(lock_path)
        notify(
            f"TFM {mode_label} interrumpido",
            "Script detenido por señal del sistema",
            priority=4,
            tags=("no_entry",),
            topic=ntfy_topic,
        )
        sys.exit(130)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        return _run(args, ntfy_topic=ntfy_topic, mode_label=mode_label)
    finally:
        if not args.dry_run:
            release_lock(lock_path)


def _run(args: argparse.Namespace, *, ntfy_topic: str, mode_label: str) -> int:
    notify(
        f"TFM {mode_label} iniciado",
        f"Script arrancado — {utcnow()}",
        priority=3,
        tags=("rocket", "computer"),
        topic=ntfy_topic,
    )

    # --validation-only: skip experiments, validate all existing results
    if args.validation_only:
        batch_dirs = collect_all_experiment_batch_dirs(RESULTS_DIR)
        print(f"[validation-only] {len(batch_dirs)} batch dirs encontrados en {RESULTS_DIR}")
        return _run_validation_phase(
            batch_dirs,
            args=args,
            ntfy_topic=ntfy_topic,
            mode_label=mode_label,
        )

    produced_batch_dirs = _run_experiments(args, ntfy_topic=ntfy_topic, mode_label=mode_label)

    if not args.skip_validation and produced_batch_dirs:
        rc = _run_validation_phase(
            produced_batch_dirs,
            args=args,
            ntfy_topic=ntfy_topic,
            mode_label=mode_label,
        )
    else:
        rc = 0

    return rc


# ---------------------------------------------------------------------------
# Experiment phase
# ---------------------------------------------------------------------------


def _run_experiments(
    args: argparse.Namespace, *, ntfy_topic: str, mode_label: str
) -> list[Path]:
    """Run all sub-batches and return the list of produced batch result dirs."""
    configs = discover_configs(BATCHES_DIR, gpt_only=args.gpt_only)
    if not configs:
        mode = "gpt-5.4" if args.gpt_only else "Ollama (excluye gpt-5.4)"
        print(f"ERROR: No se encontraron configs en {BATCHES_DIR} para el modo {mode}")
        return []

    live_sizes = {} if args.gpt_only else get_ollama_model_sizes_mib(OLLAMA_HOST)
    model_vram = {**live_sizes, **DEFAULT_MODEL_VRAM_MIB}

    openai_api_key = os.environ.get("OPENAI_API_KEY", "") if args.gpt_only else ""

    with tempfile.TemporaryDirectory(prefix="exp_subbatches_") as tmp_str:
        tmp_dir = Path(tmp_str)

        all_subs: list[Path] = []
        for cfg in configs:
            all_subs.extend(split_by_project(cfg, tmp_dir))

        if args.start_from:
            idx = next((i for i, p in enumerate(all_subs) if args.start_from in p.stem), None)
            if idx is None:
                print(f"ERROR: No hay sub-batch que contenga '{args.start_from}'.")
                print("Sub-batches disponibles:")
                for p in all_subs:
                    print(f"  {p.stem}")
                return []
            all_subs = all_subs[idx:]

        sub_batches: list[SubBatch] = []
        for sub in all_subs:
            sub_data = yaml.safe_load(sub.read_text())
            name: str = sub_data.get("name") or sub.stem
            model: str = sub_data.get("global", {}).get("llm", {}).get("model") or "unknown"
            skip_reason: str | None = None
            if not args.force:
                existing = find_completed_batch(name, RESULTS_DIR)
                if existing:
                    skip_reason = f"done -> {existing.name}"
            sub_batches.append(SubBatch(path=sub, name=name, model=model, skip_reason=skip_reason))

        to_run = sum(1 for b in sub_batches if b.skip_reason is None)
        to_skip = len(sub_batches) - to_run

        _print_plan_header(sub_batches, to_run, to_skip, args, model_vram)

        if args.dry_run:
            print("--dry-run: nada ejecutado.")
            return []

        for b in sub_batches:
            if b.skip_reason:
                print(f"SKIP {b.name}  ({b.skip_reason})")

        pending = [b for b in sub_batches if b.skip_reason is None]
        passed: list[str] = []
        failed: list[str] = []
        produced_dirs: list[Path] = []
        total_to_run = len(pending)
        completed = 0
        completed_since_notify = 0

        while pending:
            if args.gpt_only:
                # GPT mode: sequential, with balance check before each batch
                next_batch = pending[0]
                if openai_api_key:
                    can_continue, remaining = check_openai_balance(openai_api_key)
                    if not can_continue:
                        msg = f"Saldo insuficiente: ${remaining:.2f} < ${OPENAI_MIN_BALANCE_USD}"
                        print(f"[balance] STOP — {msg}", file=sys.stderr)
                        notify(
                            "TFM GPT: Saldo insuficiente",
                            msg,
                            priority=5,
                            tags=("warning", "rotating_light"),
                            topic=ntfy_topic,
                        )
                        break
                    if remaining is not None:
                        print(f"[balance] Saldo disponible: ${remaining:.2f}")
                pending.pop(0)
            else:
                # Ollama mode: VRAM-aware scheduling
                free_vram = get_free_vram_mib()
                ollama_vram = get_ollama_loaded_vram_mib(OLLAMA_HOST)
                next_batch = select_next_batch(pending, free_vram, ollama_vram, model_vram)

                if next_batch is None:
                    vram_info = (
                        f"free: {free_vram} MiB, Ollama: {ollama_vram} MiB"
                        if free_vram is not None
                        else "VRAM desconocida"
                    )
                    print(f"[GPU] {utcnow()} — Sin modelo que quepa ({vram_info}). "
                          f"Esperando {args.gpu_poll}s...")
                    time.sleep(args.gpu_poll)
                    continue

                pending.remove(next_batch)

            completed += 1
            completed_since_notify += 1
            start_mtime = time.time()

            vram_line = ""
            if not args.gpt_only:
                free_vram = get_free_vram_mib()
                ollama_vram = get_ollama_loaded_vram_mib(OLLAMA_HOST)
                vram_line = (
                    f"  Free VRAM : {free_vram} MiB  |  Ollama loaded : {ollama_vram} MiB"
                    if free_vram is not None
                    else "  Free VRAM : desconocida (nvidia-smi no disponible)"
                )

            print()
            print("-" * 64)
            print(f"[{completed}/{total_to_run}] Running : {next_batch.name}")
            print(f"  Model   : {next_batch.model}")
            if vram_line:
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
                new_dir = find_produced_batch_dir(next_batch.name, RESULTS_DIR, start_mtime)
                if new_dir:
                    produced_dirs.append(new_dir)
            else:
                failed.append(next_batch.name)
                print(f"  FAILED  : {next_batch.name} (exit {result.returncode}) — {utcnow()}",
                      file=sys.stderr)
                notify(
                    f"TFM {mode_label} FALLO: {next_batch.name}",
                    f"exit {result.returncode} — {utcnow()}",
                    priority=5,
                    tags=("warning", "rotating_light"),
                    topic=ntfy_topic,
                )

            # ntfy cada 5 batches completados (éxito o fallo)
            if completed_since_notify >= 5:
                notify(
                    f"TFM {mode_label}: {completed}/{total_to_run} batches completados",
                    f"{len(passed)} OK, {len(failed)} fallidos — {utcnow()}",
                    priority=3,
                    tags=("heavy_check_mark",),
                    topic=ntfy_topic,
                )
                completed_since_notify = 0

        _print_summary(passed, failed)

        notify(
            f"TFM {mode_label}: Experimentos completados",
            f"{len(passed)} OK, {len(failed)} fallidos — {utcnow()}",
            priority=4,
            tags=("tada",),
            topic=ntfy_topic,
        )

        return produced_dirs


# ---------------------------------------------------------------------------
# Validation phase
# ---------------------------------------------------------------------------


def _run_validation_phase(
    batch_dirs: list[Path],
    *,
    args: argparse.Namespace,
    ntfy_topic: str,
    mode_label: str,
) -> int:
    total = len(batch_dirs)
    print()
    print("=" * 64)
    print(f"  Fase de validación — {total} batch dirs")
    print("=" * 64)

    if args.dry_run:
        for bd in batch_dirs:
            print(f"  [dry-run] validar: {bd.name}")
        print(f"\n[dry-run] {total} invocaciones copilot previstas, "
              f"{args.validation_wait}s entre cada una (~{total * args.validation_wait // 60} min total)")
        return 0

    notify(
        f"TFM {mode_label}: Validacion iniciada ({total} batches)",
        f"Tiempo estimado: ~{total * args.validation_wait // 60} min — {utcnow()}",
        priority=3,
        tags=("hourglass_flowing_sand",),
        topic=ntfy_topic,
    )

    validation_failed: list[str] = []

    for i, batch_dir in enumerate(batch_dirs):
        ok = run_validation(batch_dir, dry_run=args.dry_run, ntfy_topic=ntfy_topic)
        if ok:
            notify(
                f"TFM {mode_label}: Validado batch {i + 1}/{total}",
                batch_dir.name,
                priority=3,
                tags=("heavy_check_mark",),
                topic=ntfy_topic,
            )
        else:
            validation_failed.append(batch_dir.name)

        if i < total - 1:
            print(f"  [validación] Esperando {args.validation_wait}s antes del siguiente batch...")
            time.sleep(args.validation_wait)

    ok_count = total - len(validation_failed)
    final_priority = 4 if not validation_failed else 5
    final_tags = ("partying_face",) if not validation_failed else ("triangular_flag_on_post", "warning")
    notify(
        f"TFM {mode_label} completado: {ok_count}/{total} validados",
        f"{len(validation_failed)} con errores — {utcnow()}",
        priority=final_priority,
        tags=final_tags,
        topic=ntfy_topic,
    )

    if validation_failed:
        print("\nValidaciones fallidas:")
        for name in validation_failed:
            print(f"  x {name}")
        return 1
    return 0


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _print_plan_header(
    sub_batches: list[SubBatch],
    to_run: int,
    to_skip: int,
    args: argparse.Namespace,
    model_vram: dict[str, int],
) -> None:
    mode = "GPT (gpt-5.4-mini)" if args.gpt_only else "Ollama"
    print("=" * 64)
    print(f"  Experimento TFM — {mode} — {utcnow()}")
    print(f"  Sub-batches : {len(sub_batches)}  |  Run : {to_run}  |  Skip : {to_skip}")
    if not args.gpt_only:
        print(f"  GPU poll interval : {args.gpu_poll}s")
        print(f"  Model VRAM estimates (MiB): {model_vram}")
    print("=" * 64)
    print()
    print("Plan de ejecución:")
    for b in sub_batches:
        tag = f"SKIP ({b.skip_reason})" if b.skip_reason else "RUN"
        print(f"  [{tag:<42}] {b.name}  [{b.model}]")
    print()


def _print_summary(passed: list[str], failed: list[str]) -> None:
    print()
    print("=" * 64)
    print(f"  Resumen experimentos — {utcnow()}")
    print("=" * 64)
    print(f"OK ({len(passed)}):")
    for p in passed:
        print(f"  ✓ {p}")
    print(f"Fallidos ({len(failed)}):")
    for f in failed:
        print(f"  ✗ {f}")
    print()
    print("Para agregar resultados:")
    print("  make aggregate OUT=results/experiment.db BATCH_DIRS='results/batch-experiment-*'")


if __name__ == "__main__":
    sys.exit(main())
