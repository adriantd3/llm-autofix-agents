from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from llm_autofix_agents.batch.config import (
    BatchConfig,
    BugEntry,
    DatasetConfig,
    expand_bugs,
    load_batch_config,
    load_dataset_config,
)
from llm_autofix_agents.batch.prompt import generate_prompt
from llm_autofix_agents.batch.summary import BatchSummary, BugRunResult, new_batch_id
from llm_autofix_agents.datasets.base import DatasetPreparationContext, PreparedExecutionCase
from llm_autofix_agents.datasets.registry import get as get_adapter
from llm_autofix_agents.llm.settings import _load_dotenv_values

logger = logging.getLogger(__name__)


class BatchRunner:
    def __init__(self, compose_file: Path, project_dir: Path, results_dir: Path | None = None):
        self.compose_file = compose_file.resolve()
        self.project_dir = project_dir.resolve()
        self.results_dir = results_dir or (project_dir / "results").resolve()

    def run_batch(self, config_path: Path, *, dry_run: bool = False) -> BatchSummary:
        config, dataset_path = load_batch_config(config_path)
        dataset = load_dataset_config(dataset_path)
        bugs = expand_bugs(config, dataset)

        if dry_run:
            self._print_dry_run(config, dataset, bugs)
            return self._build_summary(config, dataset, [], None, None)

        batch_id = new_batch_id(config.name)
        batch_dir = self.results_dir / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)

        workspace_root = self.project_dir / "benchmark-workspaces" / batch_id
        workspace_root.mkdir(parents=True, exist_ok=True)
        container_workspace_root = f"/benchmark-workspaces/{batch_id}"

        logger.info(
            "Starting batch '%s' (%s) with %d bugs from dataset '%s'",
            config.name,
            batch_id,
            len(bugs),
            dataset.name,
        )

        service = "bugsinpy-runner" if dataset.type == "bugsinpy" else "runner"
        self._docker_build(service)

        settings = config.global_settings
        target_model = settings.llm.model
        all_models = [target_model]
        if settings.llm.agent_models:
            all_models.extend(settings.llm.agent_models.values())
        all_models = list(dict.fromkeys(all_models))
        self._evict_stale_ollama_models(all_models, provider=settings.llm.provider)

        adapter = get_adapter(dataset.type)
        context = DatasetPreparationContext(
            dataset=dataset,
            batch=config,
            batch_id=batch_id,
            project_dir=self.project_dir,
            compose_file=self.compose_file,
            host_workspace_root=workspace_root,
            container_workspace_root=container_workspace_root,
        )

        started_at = datetime.now(UTC)
        results: list[BugRunResult] = []

        for i, bug in enumerate(bugs, 1):
            logger.info("[%d/%d] Preparing bug '%s'", i, len(bugs), bug.id)
            case: PreparedExecutionCase | None = None
            try:
                case = adapter.prepare_case(context, bug)
            except Exception as exc:
                logger.error("[%d/%d] Preparation failed for '%s': %s", i, len(bugs), bug.id, exc)
                results.append(
                    BugRunResult(
                        bug_id=bug.id,
                        status="infra_failure",
                        error_message=str(exc),
                    )
                )
                self._log_bug_result(bug.id, results[-1], i, len(bugs))
                continue

            logger.info("[%d/%d] Running bug '%s'", i, len(bugs), bug.id)
            result = self._run_case(case, config, batch_dir, dataset)
            results.append(result)
            self._log_bug_result(bug.id, result, i, len(bugs))
            self._cleanup_case(case, config)

        completed_at = datetime.now(UTC)

        summary = self._build_summary(config, dataset, results, started_at, completed_at)
        self._save_summary(summary, batch_dir)
        return summary

    def _run_case(
        self,
        case: PreparedExecutionCase,
        config: BatchConfig,
        batch_dir: Path,
        dataset: DatasetConfig,
    ) -> BugRunResult:
        settings = config.global_settings

        error_output: str | None = None
        if settings.capture_errors:
            error_output = self._capture_error_output_in_container(case)

        prompt = ""
        if settings.prompt_template is not None:
            prompt = generate_prompt(case, settings.prompt_template, error_output)
        agent_models = settings.llm.resolve_agent_models(settings.architecture)
        env = self._build_env(case, config, prompt, agent_models, batch_dir, dataset)

        started = datetime.now(UTC)
        process = self._docker_run(env, settings.timeout_seconds, case.runner_service)
        duration = (datetime.now(UTC) - started).total_seconds()

        result = self._parse_result(case.case_id, process, duration)

        if result.run_id:
            dest_name = self._rename_run_dir(batch_dir, result.run_id, case, settings)
            if dest_name:
                self._merge_into_batch_db(batch_dir, dest_name)
        elif result.status == "timed_out":
            # The container was killed before it could write its JSON output, so
            # run_id is None. Try to find the orphan run-TIMESTAMP-hash directory
            # that was created at the start of the run and rename it correctly.
            orphan_run_id = self._find_orphan_run_dir(batch_dir, started)
            if orphan_run_id:
                # Preserve correlation between the batch summary entry and the
                # on-disk run directory / SQLite rows even though the container
                # never produced the final JSON envelope.
                result.run_id = orphan_run_id
                dest_name = self._rename_run_dir(batch_dir, orphan_run_id, case, settings)
                if dest_name:
                    self._merge_into_batch_db(batch_dir, dest_name)
                    self._finalize_timed_out_run(batch_dir, dest_name, duration)

        return result

    def _capture_error_output_in_container(
        self,
        case: PreparedExecutionCase,
        timeout_seconds: int = 60,
    ) -> str | None:
        container_name = f"autofix-capture-{uuid.uuid4().hex[:12]}"
        uid = os.getuid()
        gid = os.getgid()
        wrapped = f"cd {shlex.quote(case.container_workspace)} && {case.test_command}"
        cmd = [
            "docker",
            "compose",
            "-f",
            str(self.compose_file),
            "run",
            "--rm",
            "-T",
            "--name",
            container_name,
            "--user",
            f"{uid}:{gid}",
            case.runner_service,
            "sh",
            "-c",
            wrapped,
        ]
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_dir),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            parts: list[str] = []
            if result.stdout:
                parts.append(result.stdout.strip())
            if result.stderr:
                parts.append(result.stderr.strip())
            combined = "\n".join(parts)
            if not combined:
                return None
            return combined[-4000:] if len(combined) > 4000 else combined
        except subprocess.TimeoutExpired:
            self._force_kill_container(container_name)
            logger.warning(
                "Error capture timed out in container for test command: %s",
                case.test_command,
            )
            return None
        except Exception:
            self._force_kill_container(container_name)
            logger.warning(
                "Error capture failed in container for test command: %s",
                case.test_command,
                exc_info=True,
            )
            return None

    def _force_kill_container(self, container_name: str) -> None:
        """Send SIGKILL to a named container immediately, then wait for removal."""
        try:
            subprocess.run(
                ["docker", "kill", container_name],
                capture_output=True,
                timeout=10,
            )
            logger.info("Container '%s' killed", container_name)
        except Exception:
            logger.warning("Failed to kill container '%s'", container_name, exc_info=True)

    def _docker_build(self, service: str) -> None:
        logger.info("Building Docker image for service '%s'...", service)
        result = subprocess.run(
            ["docker", "compose", "-f", str(self.compose_file), "build", service],
            cwd=str(self.project_dir),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error("Docker build failed:\n%s", result.stderr)
            raise RuntimeError(f"Docker build failed: {result.stderr[:500]}")
        logger.info("Docker image for service '%s' built successfully", service)

    def _evict_stale_ollama_models(self, keep_models: list[str], *, provider: str = "ollama") -> None:
        """Stop any Ollama models that are NOT in keep_models to free GPU VRAM.

        Prevents CUDA OOM when switching between models of different sizes
        (e.g., qwen3.5:9b still loaded when qwen3.5:27b tries to start).
        Uses the native Ollama API on localhost:11434 (not the Docker-forwarded
        OpenAI-compatible proxy on port 11500).
        """
        if provider != "ollama":
            return

        dotenv_values = _load_dotenv_values(Path(".env"))
        combined_env = {**dotenv_values, **os.environ}
        ollama_host = combined_env.get("OLLAMA_HOST", "http://localhost:11434")
        if not ollama_host.startswith(("http://", "https://")):
            ollama_host = f"http://{ollama_host}"
        ps_url = f"{ollama_host.rstrip('/')}/api/ps"

        try:
            resp = httpx.get(ps_url, timeout=5)
            resp.raise_for_status()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            logger.warning("Could not query Ollama for loaded models: %s", exc)
            return
        except Exception as exc:
            logger.warning("Could not query Ollama for loaded models: %s", exc)
            return

        loaded = resp.json().get("models", [])
        if not loaded:
            return

        keep_normalized = {m.split(":")[0].lower(): m for m in keep_models}
        keep_full = {m.lower() for m in keep_models}
        evicted = []
        for model_info in loaded:
            name = model_info.get("name", "")
            if not name:
                continue
            name_lower = name.lower()
            base_name = name.split(":")[0].lower()
            if name_lower in keep_full or base_name in keep_normalized:
                continue
            unload_url = f"{ollama_host.rstrip('/')}/api/unload"
            try:
                httpx.post(unload_url, json={"model": name}, timeout=10)
                evicted.append(name)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                logger.warning("Failed to evict Ollama model '%s': %s", name, exc)

        if evicted:
            logger.info("Evicted stale Ollama models to free VRAM: %s", ", ".join(evicted))

    def _docker_run(
        self,
        env: dict[str, str],
        timeout_seconds: int,
        service: str,
    ) -> subprocess.CompletedProcess[str]:
        container_name = f"autofix-{uuid.uuid4().hex[:12]}"
        cmd = [
            "docker",
            "compose",
            "-f",
            str(self.compose_file),
            "run",
            "--rm",
            "-T",
            "--name",
            container_name,
        ]
        # env is already curated by _build_env(); pass everything explicitly.
        for key, value in sorted(env.items()):
            cmd.extend(["-e", f"{key}={value}"])
        cmd.append(service)
        cmd.extend(["uv", "run", "python", "-m", "llm_autofix_agents.batch.executor"])

        with subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(self.project_dir),
        ) as proc:
            try:
                stdout, stderr = proc.communicate(timeout=timeout_seconds)
                return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
            except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
                timed_out = isinstance(exc, subprocess.TimeoutExpired)
                if timed_out:
                    logger.warning(
                        "Container '%s' timed out after %ds — killing container...",
                        container_name,
                        timeout_seconds,
                    )
                else:
                    logger.warning("Interrupted — killing container '%s'...", container_name)
                proc.kill()
                self._force_kill_container(container_name)
                try:
                    stdout, stderr = proc.communicate(timeout=15)
                except subprocess.TimeoutExpired:
                    stdout, stderr = "", ""
                if not timed_out:
                    raise
                return subprocess.CompletedProcess(cmd, 124, stdout or "", stderr or "")

    def _build_env(
        self,
        case: PreparedExecutionCase,
        config: BatchConfig,
        prompt: str,
        agent_models: dict[str, str],
        batch_dir: Path,
        dataset: DatasetConfig,
    ) -> dict[str, str]:
        """Build a clean, explicit environment dict for the container.

        No host env pollution — only batch config + curated API keys.
        """
        settings = config.global_settings
        batch_name = batch_dir.name
        env: dict[str, str] = {
            "HOST_UID": str(os.getuid()),
            "HOST_GID": str(os.getgid()),
            "RUN_REPOSITORY": case.container_workspace,
            "RUN_BRANCH": "",
            "RUN_ARCHITECTURE": settings.architecture.value,
            "RUN_AGENT_MODELS": json.dumps(agent_models),
            "RUN_TEST_COMMAND": case.test_command,
            "RUN_DATASET_TYPE": case.dataset_type,
            "RUN_DATASET_NAME": case.dataset_name,
            "RUN_PROBLEM_ID": case.case_id,
            "RUN_MAX_TURNS": str(settings.llm.max_turns),
            "LLM_PROVIDER": settings.llm.provider,
            "LLM_MODEL": settings.llm.model,
            "AUTOFIX_MAX_ITERATIONS": str(settings.max_iterations),
            "AUTOFIX_RESULTS_DIR": f"/results/{batch_name}",
            "AUTOFIX_INTERACTIVE": "false",
        }
        if settings.llm.extra_body is not None:
            env["LLM_EXTRA_BODY"] = json.dumps(settings.llm.extra_body)
        if settings.iteration_timeout_seconds is not None:
            env["AUTOFIX_ITERATION_TIMEOUT_SECONDS"] = str(settings.iteration_timeout_seconds)
        if case.dataset_type == "bugsinpy":
            compile_required = dataset.tooling.get("compile_required", True)
            env["RUN_BUGSINPY_COMPILE_REQUIRED"] = "true" if compile_required else "false"
        if prompt:
            env["RUN_BOOTSTRAP_PROMPT"] = prompt
        # Propagate API keys from host env + .env file (secrets only)
        dotenv_values = _load_dotenv_values(Path(".env"))
        combined_env = {**dotenv_values, **os.environ}
        for key, value in combined_env.items():
            if "API_KEY" in key and value:
                env[key] = value
        return env

    def _parse_result(
        self,
        case_id: str,
        process: subprocess.CompletedProcess[str],
        duration_seconds: float,
    ) -> BugRunResult:
        if process.returncode == 124:
            return BugRunResult(
                bug_id=case_id,
                status="timed_out",
                duration_seconds=duration_seconds,
                exit_code=124,
                error_message="Container timed out",
            )

        if process.returncode == 2:
            return BugRunResult(
                bug_id=case_id,
                status="infra_failure",
                duration_seconds=duration_seconds,
                exit_code=process.returncode,
                error_message=_truncate(process.stderr, 1000),
            )

        if process.returncode not in (0, 1):
            return BugRunResult(
                bug_id=case_id,
                status="infra_failure",
                duration_seconds=duration_seconds,
                exit_code=process.returncode,
                error_message=_truncate(process.stderr, 1000),
            )

        payload = _parse_json_output(process.stdout)
        if payload is None:
            return BugRunResult(
                bug_id=case_id,
                status="infra_failure",
                duration_seconds=duration_seconds,
                exit_code=process.returncode,
                error_message=_truncate(process.stderr, 1000) or "Failed to parse container output",
            )

        output = payload.get("output", {})
        identity = output.get("identity", {})
        return BugRunResult(
            bug_id=case_id,
            status=output.get("status", "unknown"),
            run_id=identity.get("run_id"),
            duration_seconds=duration_seconds,
            iterations=identity.get("iteration"),
            exit_code=process.returncode,
        )

    def _find_orphan_run_dir(self, batch_dir: Path, started: datetime) -> str | None:
        """Return the name of the orphan run-TIMESTAMP-hash dir left by a timed-out container.

        Scans batch_dir for directories whose name starts with "run-" and whose
        mtime is at or after `started`. Returns the name only when exactly one
        candidate is found — ambiguous results are left untouched.
        """
        try:
            candidates = [
                d for d in batch_dir.iterdir()
                if d.is_dir()
                and d.name.startswith("run-")
                and d.stat().st_mtime >= started.timestamp()
            ]
        except OSError:
            return None
        if len(candidates) == 1:
            return candidates[0].name
        return None

    def _rename_run_dir(
        self, batch_dir: Path, run_id: str, case: PreparedExecutionCase, settings: Any
    ) -> str | None:
        src = batch_dir / run_id
        if not src.exists():
            logger.warning("Run directory %s not found for renaming", src)
            return None

        safe_model = _sanitize_dir_name(settings.llm.model)
        dest_name = f"{case.case_id}-{settings.architecture.value}-{safe_model}"
        dest = batch_dir / dest_name

        counter = 1
        original_dest = dest
        while dest.exists():
            dest = batch_dir / f"{original_dest.name}-{counter}"
            dest_name = dest.name
            counter += 1

        src.rename(dest)
        logger.info("Run directory renamed: %s -> %s", src.name, dest.name)
        self._update_observability_paths(batch_dir, run_id, dest_name)
        return dest_name

    def _merge_into_batch_db(self, batch_dir: Path, dest_name: str) -> None:
        run_db = batch_dir / dest_name / "run.db"
        if not run_db.exists():
            return
        try:
            from llm_autofix_agents.observability.sqlite_store import SQLiteObservabilityStore

            batch_db_path = batch_dir / "batch.db"
            batch_store = SQLiteObservabilityStore(db_path=batch_db_path)
            batch_store.initialize()
            batch_store.merge_from(run_db)
            logger.debug("Merged run DB %s into batch.db", run_db.name)
        except Exception:
            logger.warning("Failed to merge run DB into batch.db", exc_info=True)

    def _finalize_timed_out_run(
        self, batch_dir: Path, dest_name: str, duration_seconds: float
    ) -> None:
        """Write a synthetic summary.json and update DB records for a timed-out run.

        Reconstructs token totals from completed iteration_finished events in
        events.jsonl so the run has meaningful data even though the container
        was killed before RunFinalizer could execute.
        """
        run_dir = batch_dir / dest_name
        events_file = run_dir / "events.jsonl"
        if not events_file.exists():
            return

        run_id: str | None = None
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0
        iterations = 0
        changed_files_count = 0
        try:
            with events_file.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if run_id is None:
                        run_id = event.get("run_id")
                    if event.get("event") == "iteration_finished":
                        iterations += 1
                        total_input_tokens += event.get("input_tokens", 0)
                        total_output_tokens += event.get("output_tokens", 0)
                        total_tokens += event.get("total_tokens", 0)
                        changed_files_count = max(
                            changed_files_count, event.get("changed_files_count", 0)
                        )
        except OSError:
            logger.warning("Could not read events.jsonl for timed-out run %s", dest_name)
            return

        if run_id is None:
            logger.warning("No run_id found in events.jsonl for timed-out run %s", dest_name)
            return

        batch_name = batch_dir.name
        summary_path = run_dir / "summary.json"
        db_summary_path = f"/results/{batch_name}/{dest_name}/summary.json"
        live_log_path = run_dir / "live.md"
        db_live_log_path = (
            f"/results/{batch_name}/{dest_name}/live.md" if live_log_path.exists() else None
        )

        try:
            from llm_autofix_agents.observability.summary import write_summary

            write_summary(
                summary_path=summary_path,
                run_id=run_id,
                status="timed_out",
                stop_reason="timed_out",
                duration_seconds=duration_seconds,
                iterations=iterations,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                total_tokens=total_tokens,
                changed_files_count=changed_files_count,
                observability_db=f"/results/{batch_name}/{dest_name}/run.db",
                live_log=db_live_log_path,
            )
        except Exception:
            logger.warning(
                "Failed to write summary.json for timed-out run %s", dest_name, exc_info=True
            )

        finished_at = datetime.now(UTC).isoformat()
        try:
            from llm_autofix_agents.observability.models import RunFinishedRecord
            from llm_autofix_agents.observability.sqlite_store import SQLiteObservabilityStore

            record = RunFinishedRecord(
                run_id=run_id,
                finished_at=finished_at,
                final_status="timed_out",
                stop_reason="timed_out",
                duration_seconds=duration_seconds,
                total_iterations=iterations,
                total_input_tokens=total_input_tokens,
                total_output_tokens=total_output_tokens,
                total_tokens=total_tokens,
                files_changed_count=changed_files_count,
                resolved=False,
                live_log_path=db_live_log_path,
                summary_path=db_summary_path,
            )
            run_db = run_dir / "run.db"
            if run_db.exists():
                SQLiteObservabilityStore(db_path=run_db).update_run_finished(record)
            batch_db_path = batch_dir / "batch.db"
            batch_store = SQLiteObservabilityStore(db_path=batch_db_path)
            batch_store.initialize()
            batch_store.update_run_finished(record)
            logger.info("Finalized timed-out run %s: %d tokens from %d iterations", dest_name, total_tokens, iterations)
        except Exception:
            logger.warning(
                "Failed to update DB for timed-out run %s", dest_name, exc_info=True
            )

    def _update_observability_paths(self, batch_dir: Path, run_id: str, dest_name: str) -> None:
        # Update path columns in the per-run DB after the run directory is renamed.
        run_db = batch_dir / dest_name / "run.db"
        if not run_db.exists():
            return
        try:
            import sqlite3

            conn = sqlite3.connect(str(run_db))
            cursor = conn.cursor()
            batch_name = batch_dir.name
            old_prefix = f"/results/{batch_name}/{run_id}"
            new_prefix = f"/results/{batch_name}/{dest_name}"
            for col in ("live_log_path", "diff_path", "summary_path"):
                cursor.execute(
                    f"UPDATE runs SET {col} = REPLACE({col}, ?, ?) WHERE {col} LIKE ?",  # noqa: S608
                    (old_prefix, new_prefix, f"{old_prefix}%"),
                )
            conn.commit()
            conn.close()
            logger.debug("Updated observability paths for run %s -> %s", run_id, dest_name)
        except Exception:
            logger.warning("Failed to update observability paths after rename", exc_info=True)

    def _print_dry_run(self, config: BatchConfig, dataset: DatasetConfig, bugs: list[BugEntry]) -> None:
        settings = config.global_settings
        agent_models = settings.llm.resolve_agent_models(settings.architecture)
        print(f"Batch: {config.name}")
        print(f"Dataset: {dataset.name} (type={dataset.type})")
        print(f"Architecture: {settings.architecture.value}")
        print(f"Model: {settings.llm.model}")
        print(f"Agent models: {agent_models}")
        print(f"Max iterations: {settings.max_iterations}")
        print(f"Timeout: {settings.timeout_seconds}s")
        print(f"Bugs ({len(bugs)}):")
        for bug in bugs:
            tc = dataset.resolve_test_command(bug)
            print(f"  - {bug.id} ({tc})")
        print(f"\nCapture errors: {settings.capture_errors}")

    def _log_bug_result(self, bug_id: str, result: BugRunResult, index: int, total: int) -> None:
        status_emoji = {
            "success": "+",
            "failed": "-",
            "partial": "-",  # legacy: merged into failed
            "timed_out": "!",
            "infra_failure": "x",
        }.get(result.status, "?")
        logger.info(
            "[%d/%d] %s [%s] %s (%.1fs)",
            index,
            total,
            status_emoji,
            result.status,
            bug_id,
            result.duration_seconds,
        )

    def _build_summary(
        self,
        config: BatchConfig,
        dataset: DatasetConfig,
        results: list[BugRunResult],
        started_at: datetime | None,
        completed_at: datetime | None,
    ) -> BatchSummary:
        successful = sum(1 for r in results if r.status == "success")
        failed = sum(1 for r in results if r.status in ("failed", "partial"))  # partial is legacy
        timed_out = sum(1 for r in results if r.status == "timed_out")
        infra_failures = sum(1 for r in results if r.status == "infra_failure")
        return BatchSummary(
            batch_name=config.name,
            config_path=str(config.name),
            dataset_name=dataset.name,
            architecture=config.global_settings.architecture.value,
            model=config.global_settings.llm.model,
            provider=config.global_settings.llm.provider,
            started_at=started_at or datetime.now(UTC),
            completed_at=completed_at or datetime.now(UTC),
            total_bugs=len(results),
            successful=successful,
            failed=failed,
            timed_out=timed_out,
            infra_failures=infra_failures,
            results=results,
        )

    def _save_summary(self, summary: BatchSummary, batch_dir: Path) -> Path:
        summary_path = batch_dir / "summary.json"
        summary_path.write_text(
            summary.model_dump_json(indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        logger.info("Batch summary saved to %s", summary_path)
        return summary_path

    def _cleanup_case(self, case: PreparedExecutionCase, config: BatchConfig) -> None:
        if not config.global_settings.cleanup_workspaces:
            return
        for path in case.cleanup_paths:
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
                logger.debug("Cleaned up workspace: %s", path)


def _parse_json_output(stdout: str) -> dict[str, Any] | None:
    try:
        data = json.loads(stdout)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _sanitize_dir_name(name: str) -> str:
    return name.replace("/", "-").replace(":", "-").replace(" ", "-")
