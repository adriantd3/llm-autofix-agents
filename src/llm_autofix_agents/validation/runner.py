from __future__ import annotations

import asyncio
import logging
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from agents import Agent, Runner

from llm_autofix_agents.llm.agent_factory import build_model
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.observability.models import RunValidationRecord
from llm_autofix_agents.observability.sqlite_store import SQLiteObservabilityStore
from llm_autofix_agents.validation.canonical import resolve_canonical_patch
from llm_autofix_agents.validation.models import RunValidationInput, ValidatorOutput
from llm_autofix_agents.validation.prompt import build_validator_prompt, get_system_prompt

logger = logging.getLogger(__name__)

# Maximum characters of live log to include as test output context.
_MAX_LIVE_LOG_CHARS = 6000


@dataclass(frozen=True)
class ValidationResult:
    run_id: str
    verdict: str
    confidence: float | None
    justification: str | None
    skipped: bool = False
    skip_reason: str | None = None


class ValidationRunner:
    """Validates completed APR runs by calling an LLM judge.

    Reads run artefacts from the SQLite DB, builds validation context,
    calls the validator agent, and persists the verdict back to the DB.
    """

    def __init__(
        self,
        *,
        db_path: Path,
        llm_settings: LLMSettings,
        canonical_root: Path | None = None,
        force_revalidate: bool = False,
    ) -> None:
        self._store = SQLiteObservabilityStore(db_path=db_path)
        self._db_path = db_path
        self._llm_settings = llm_settings
        self._canonical_root = canonical_root
        self._force_revalidate = force_revalidate
        self._agent: Agent[ValidatorOutput] | None = None

    def validate_all(self) -> list[ValidationResult]:
        """Validate every run in the DB that does not yet have a verdict."""
        run_ids = self._query_run_ids()
        results = []
        for run_id in run_ids:
            result = self.validate_run(run_id)
            results.append(result)
        return results

    def validate_run(self, run_id: str) -> ValidationResult:
        """Validate a single run and store the verdict."""
        if not self._force_revalidate and self._already_validated(run_id):
            logger.info("Skipping %s: already validated", run_id)
            return ValidationResult(run_id=run_id, verdict="", confidence=None, justification=None,
                                    skipped=True, skip_reason="already_validated")

        ctx = self._gather_context(run_id)
        if ctx is None:
            return ValidationResult(run_id=run_id, verdict="", confidence=None, justification=None,
                                    skipped=True, skip_reason="run_not_found")

        logger.info("Validating run %s (bug=%s test_exit_code=%s)", run_id, ctx.problem_id, ctx.test_exit_code)

        try:
            output = asyncio.run(self._call_llm(ctx))
        except Exception:
            logger.exception("LLM validation failed for run %s", run_id)
            error_record = self._build_error_record(run_id)
            self._store.upsert_run_validation(error_record)
            return ValidationResult(run_id=run_id, verdict="VALIDATION_ERROR", confidence=None,
                                    justification=None, skipped=False)

        record = self._build_record(run_id, ctx, output)
        self._store.upsert_run_validation(record)
        logger.info("Verdict for %s: %s (confidence=%.2f)", run_id, output.verdict, output.confidence)

        return ValidationResult(
            run_id=run_id,
            verdict=output.verdict,
            confidence=output.confidence,
            justification=output.justification,
        )

    # ─── private helpers ──────────────────────────────────────────────────────

    def _gather_context(self, run_id: str) -> RunValidationInput | None:
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT run_id, problem_id, benchmark_name, diff_path, live_log_path, "
                "final_status, resolved FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()

        if row is None:
            return None

        problem_id: str = row["problem_id"] or run_id
        benchmark_name: str = row["benchmark_name"] or ""
        dataset_type = _infer_dataset_type(benchmark_name)

        # Read generated patch from diff_path (relative to DB directory or absolute).
        generated_patch = _read_artefact(row["diff_path"], self._db_path.parent)

        # Read test output tail from live log.
        test_output = _read_artefact(row["live_log_path"], self._db_path.parent, max_chars=_MAX_LIVE_LOG_CHARS)

        # Resolve canonical ground truth if a root was provided.
        canonical_patch = resolve_canonical_patch(
            dataset_type=dataset_type,
            problem_id=problem_id,
            canonical_root=self._canonical_root,
        )

        # Derive test_passed from the last iteration's exit code or the resolved flag.
        test_exit_code = self._query_last_test_exit_code(run_id)
        test_passed = test_exit_code == 0

        return RunValidationInput(
            run_id=run_id,
            problem_id=problem_id,
            benchmark_name=benchmark_name,
            dataset_type=dataset_type,
            test_exit_code=test_exit_code,
            generated_patch=generated_patch,
            canonical_patch=canonical_patch,
            test_output=test_output,
        )

    def _query_last_test_exit_code(self, run_id: str) -> int | None:
        with sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute(
                "SELECT test_exit_code FROM iterations "
                "WHERE run_id = ? ORDER BY iteration_index DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        return row[0] if row else None

    def _already_validated(self, run_id: str) -> bool:
        with sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute(
                "SELECT 1 FROM run_validations WHERE run_id = ? LIMIT 1",
                (run_id,),
            ).fetchone()
        return row is not None

    def _query_run_ids(self) -> list[str]:
        with sqlite3.connect(str(self._db_path)) as conn:
            rows = conn.execute(
                "SELECT run_id FROM runs WHERE final_status = 'success' ORDER BY started_at"
            ).fetchall()
        return [r[0] for r in rows]

    async def _call_llm(self, ctx: RunValidationInput) -> ValidatorOutput:
        if self._agent is None:
            model = build_model(self._llm_settings)
            self._agent = Agent(
                name="apr-validator",
                instructions=get_system_prompt(),
                model=model,
                output_type=ValidatorOutput,
            )

        user_prompt = build_validator_prompt(ctx)
        result = await Runner.run(self._agent, user_prompt, max_turns=1)
        output = result.final_output
        if not isinstance(output, ValidatorOutput):
            raise TypeError(f"Expected ValidatorOutput, got {type(output)}")
        return output

    def _build_record(self, run_id: str, ctx: RunValidationInput, output: ValidatorOutput) -> RunValidationRecord:
        validation_id = _make_validation_id(run_id, self._llm_settings.model)
        return RunValidationRecord(
            validation_id=validation_id,
            run_id=run_id,
            validated_at=datetime.now(UTC).isoformat(),
            validator_model=self._llm_settings.model,
            verdict=output.verdict,
            test_passed=output.test_passed,
            infra_fail_detected=None,
            canonical_patch_available=ctx.canonical_patch is not None,
            patch_semantically_matches=output.patch_semantically_matches,
            confidence=output.confidence,
            justification=output.justification,
        )

    def _build_error_record(self, run_id: str) -> RunValidationRecord:
        validation_id = _make_validation_id(run_id, self._llm_settings.model)
        return RunValidationRecord(
            validation_id=validation_id,
            run_id=run_id,
            validated_at=datetime.now(UTC).isoformat(),
            validator_model=self._llm_settings.model,
            verdict="VALIDATION_ERROR",
            justification="LLM validation pipeline failed — see logs for details.",
        )


# ─── module-level helpers ─────────────────────────────────────────────────────


def _infer_dataset_type(benchmark_name: str) -> str:
    name = benchmark_name.lower()
    if "quixbug" in name:
        return "quixbugs"
    if "bugsinpy" in name or "bugs-in-py" in name:
        return "bugsinpy"
    return "unknown"


def _read_artefact(
    stored_path: str | None,
    db_dir: Path,
    max_chars: int | None = None,
) -> str | None:
    if not stored_path:
        return None
    path = Path(stored_path)
    if not path.is_absolute():
        path = db_dir / path
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    if max_chars is not None and len(text) > max_chars:
        return text[-max_chars:]
    return text


def _make_validation_id(run_id: str, model: str) -> str:
    digest = sha256(f"{run_id}|{model}".encode()).hexdigest()[:16]
    return f"val-{digest}"
