#!/usr/bin/env python3
"""
validate_batch.py — LLM-as-judge validator for APR batch results.

Reads resolved runs from a consolidated batch DB, builds context from the
generated patch and the canonical solution, calls an LLM to produce a
structured verdict, and writes results to `run_validations`.

Usage:
    # Validate all unvalidated resolved runs in a DB
    uv run python .agents/skills/apr-validator/scripts/validate_batch.py \\
        --db results/quixbugs-benchmark-20260517T160729Z.db

    # Force re-validation of all resolved runs
    uv run python .agents/skills/apr-validator/scripts/validate_batch.py \\
        --db results/quixbugs-benchmark-20260517T160729Z.db --force

    # Validate a single run
    uv run python .agents/skills/apr-validator/scripts/validate_batch.py \\
        --db results/quixbugs-benchmark-20260517T160729Z.db \\
        --run-id run-20260517T121942Z-ab8baf311e

    # Use a different model (default: gpt-4.1-mini)
    uv run python .agents/skills/apr-validator/scripts/validate_batch.py \\
        --db results/quixbugs-benchmark-20260517T160729Z.db \\
        --model gpt-4o-mini

Environment:
    OPENAI_API_KEY — required for OpenAI models
    OPENAI_BASE_URL — optional, override for custom endpoints
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import openai

# ── Prompts ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert APR (Automated Program Repair) validator.

Your task: decide whether an agent-generated patch is semantically correct.

Decision tree (apply in order):
1. If the patch introduces hardcoded return values, modifies the test file, or
   silences errors without fixing the root cause → OVERFITTING
2. If a canonical (correct) program is available:
   - Patch addresses the same root cause as the canonical → CORRECT
   - Patch makes tests pass but via a different/partial approach → PLAUSIBLE
3. If no canonical is available:
   - Logic is clearly sound and addresses the root cause visible in the diff → CORRECT
   - Logic is unclear or only partially fixes the issue → PLAUSIBLE

Return ONLY valid JSON — no prose, no markdown fences:
{
  "verdict": "CORRECT | PLAUSIBLE | OVERFITTING | VALIDATION_ERROR",
  "confidence": <float 0.0-1.0>,
  "test_passed": true,
  "patch_semantically_matches": <true | false | null>,
  "justification": "<2-4 sentence explanation>"
}
"""

USER_TEMPLATE = """\
## Bug: {bug_id}
## Dataset: {dataset}
## Architecture: {arch}

---
## Agent-generated patch:

```diff
{patch}
```

---
## Canonical ground truth (correct program or canonical patch):

```
{canonical}
```

---
## Buggy program (original, before fix):

```python
{buggy}
```

Evaluate the patch following the decision tree and return a JSON verdict.
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def read_file_safe(path: Path) -> str:
    """Return file content or empty string if not found."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def collect_patches(run_dir: Path) -> str:
    """Return concatenated content of all it*.patch files, capped at 6 KB."""
    patches = sorted(run_dir.glob("it*.patch"))
    if not patches:
        return ""
    combined = "\n\n".join(p.read_text(encoding="utf-8", errors="replace") for p in patches)
    return combined[:6000]


def detect_dataset(target_repo: str) -> str:
    """Infer dataset name from the target_repo path."""
    lower = target_repo.lower()
    if "quixbug" in lower:
        return "QuixBugs"
    if "bugsinpy" in lower or any(
        proj in lower
        for proj in ["thefuck", "youtube-dl", "httpie", "pysnooper",
                     "fastapi", "tornado", "black", "tqdm", "scrapy",
                     "luigi", "ansible"]
    ):
        return "BugsInPy"
    return "unknown"


def build_quixbugs_context(bug_id: str, target_repo_abs: Path) -> tuple[str, str]:
    """Return (canonical_program, buggy_program) for a QuixBugs run."""
    canonical = read_file_safe(target_repo_abs / "correct_python_programs" / f"{bug_id}.py")
    # Note: python_programs/ may already contain the agent's fix after the run,
    # so it is only useful to understand program structure.
    buggy = read_file_safe(target_repo_abs / "python_programs" / f"{bug_id}.py")
    return canonical, buggy


def build_bugsinpy_context(bug_id: str, target_repo_abs: Path, bugsinpy_root: Path | None = None) -> tuple[str, str]:
    """
    For BugsInPy, read the canonical bug_patch.txt from the local BugsInPy repo.
    problem_id format: {project}-{number}, e.g. ansible-1, youtube-dl-3.
    """
    if bugsinpy_root and bugsinpy_root.is_dir():
        # Parse project and number from bug_id (split on last hyphen)
        number = bug_id.rsplit("-", 1)[-1]
        project = bug_id.rsplit("-", 1)[0]
        patch_path = bugsinpy_root / "projects" / project / "bugs" / number / "bug_patch.txt"
        canonical_patch = read_file_safe(patch_path)
        if canonical_patch:
            return canonical_patch, ""
    return "", ""


# ── LLM call ─────────────────────────────────────────────────────────────────

def call_llm(client: openai.OpenAI, model: str, user_msg: str) -> dict:
    """Call the model and parse the JSON verdict."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or "{}"
    # Strip accidental markdown fences if the model ignores the instruction
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    return json.loads(raw)


# ── Core validation logic ─────────────────────────────────────────────────────

def validate_run(run: dict, workspace_root: Path, client: openai.OpenAI, model: str,
                 bugsinpy_root: Path | None = None) -> dict:
    """
    Build context for a single run and call the LLM judge.

    Returns a dict with verdict, confidence, justification, etc.
    On any infrastructure error (patch not found, unreadable file) returns
    a VALIDATION_ERROR dict rather than raising.
    """
    target_repo: str = run["target_repo"] or ""
    live_log_path: str = run["live_log_path"] or ""

    # Derive run directory from live_log_path (strip leading slash, then parent)
    run_dir = (workspace_root / live_log_path.lstrip("/")).parent

    # Derive bug_id: use problem_id when available (correct for BugsInPy like
    # "PySnooper-3"), fall back to the last segment of target_repo (correct for
    # QuixBugs where the repo name IS the bug name, e.g. "gcd").
    bug_id = run.get("problem_id") or (
        Path(target_repo.rstrip("/")).name if target_repo else "unknown"
    )

    # Collect generated patch
    patch = collect_patches(run_dir)
    if not patch:
        return {
            "verdict": "VALIDATION_ERROR",
            "confidence": None,
            "test_passed": True,
            "patch_semantically_matches": None,
            "justification": f"No patch file found in run directory: {run_dir}",
        }

    # Build canonical and buggy context based on dataset
    target_repo_abs = workspace_root / target_repo.lstrip("/")
    dataset = detect_dataset(target_repo)

    if dataset == "QuixBugs":
        canonical, buggy = build_quixbugs_context(bug_id, target_repo_abs)
    elif dataset == "BugsInPy":
        canonical, buggy = build_bugsinpy_context(bug_id, target_repo_abs, bugsinpy_root)
    else:
        canonical, buggy = "", ""

    user_msg = USER_TEMPLATE.format(
        bug_id=bug_id,
        dataset=dataset,
        arch=run.get("arch", "unknown"),
        patch=patch,
        canonical=canonical[:4000] if canonical else "(not available)",
        buggy=buggy[:2000] if buggy else "(not available — see patch for changes)",
    )

    return call_llm(client, model, user_msg)


# ── DB write ─────────────────────────────────────────────────────────────────

def write_validation(conn: sqlite3.Connection, run_id: str, model: str, result: dict) -> None:
    """Upsert a validation result into run_validations."""
    patch_matches_raw = result.get("patch_semantically_matches")
    if patch_matches_raw is True:
        patch_matches = 1
    elif patch_matches_raw is False:
        patch_matches = 0
    else:
        patch_matches = None

    canonical_available = 1 if patch_matches_raw is not None else 0

    conn.execute(
        """
        INSERT OR REPLACE INTO run_validations
            (validation_id, run_id, validated_at, validator_model,
             test_passed, infra_fail_detected, canonical_patch_available,
             patch_semantically_matches, verdict, confidence, justification)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            run_id,
            datetime.now(timezone.utc).isoformat(),
            model,
            1 if result.get("test_passed", True) else 0,
            0,
            canonical_available,
            patch_matches,
            result.get("verdict", "VALIDATION_ERROR"),
            result.get("confidence"),
            result.get("justification", ""),
        ),
    )
    conn.commit()


# ── Entry point ───────────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="LLM-as-judge validator for APR batch results.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--db", required=True, metavar="PATH",
                        help="Path to the consolidated batch SQLite database.")
    parser.add_argument(
        "--workspace-root",
        default=str(Path(__file__).resolve().parents[4]),
        metavar="PATH",
        help="Repo root used to resolve relative paths stored in the DB. "
             "Defaults to the llm-autofix-agents repo root.",
    )
    parser.add_argument(
        "--bugsinpy-root",
        default=str(Path.home() / "Projects" / "BugsInPy"),
        metavar="PATH",
        help="Path to local BugsInPy repo for canonical patch resolution. "
             "Defaults to ~/Projects/BugsInPy.",
    )
    parser.add_argument("--model", default="gpt-4.1-mini", metavar="MODEL",
                        help="OpenAI model for the LLM judge (default: gpt-4.1-mini).")
    parser.add_argument("--force", action="store_true",
                        help="Re-validate runs that already have a verdict.")
    parser.add_argument("--run-id", metavar="RUN_ID",
                        help="Validate only the specified run_id.")
    parser.add_argument("--json", action="store_true",
                        help="Emit a JSON summary line at the end (useful for agent parsing).")
    return parser


def fetch_runs(conn: sqlite3.Connection, force: bool, run_id: str | None) -> list[dict]:
    """Query runs eligible for validation."""
    query = """
        SELECT r.run_id, r.target_repo, r.live_log_path,
               r.benchmark_name, r.problem_id, a.name AS arch
        FROM runs r
        JOIN architectures a ON a.architecture_id = r.architecture_id
        WHERE r.resolved = 1
          AND r.live_log_path IS NOT NULL
    """
    params: list = []

    if run_id:
        query += " AND r.run_id = ?"
        params.append(run_id)
    elif not force:
        query += " AND r.run_id NOT IN (SELECT run_id FROM run_validations)"

    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    db_path = Path(args.db)
    workspace_root = Path(args.workspace_root)
    bugsinpy_root = Path(args.bugsinpy_root) if args.bugsinpy_root else None

    if not db_path.exists():
        _fail(f"DB not found: {db_path}", args)

    if not os.environ.get("OPENAI_API_KEY"):
        _fail("OPENAI_API_KEY environment variable not set.", args)

    client = openai.OpenAI()
    conn = sqlite3.connect(db_path)

    runs = fetch_runs(conn, force=args.force, run_id=args.run_id)
    total = len(runs)

    if not args.json:
        print(f"Runs to validate: {total}")

    if total == 0:
        if args.json:
            print(json.dumps({"status": "ok", "validated": 0, "errors": 0,
                              "message": "Nothing to do. Use --force to re-validate."}))
        else:
            print("Nothing to do. Use --force to re-validate existing results.")
        conn.close()
        return

    ok = errors = 0
    results_log: list[dict] = []

    for i, run in enumerate(runs, 1):
        bug_id = run.get("problem_id") or (
            Path(run["target_repo"].rstrip("/")).name
            if run.get("target_repo")
            else "unknown"
        )
        arch = run.get("arch", "?")
        if not args.json:
            print(f"[{i}/{total}] {bug_id} ({arch}) ... ", end="", flush=True)

        try:
            result = validate_run(run, workspace_root, client, args.model, bugsinpy_root=bugsinpy_root)
            write_validation(conn, run["run_id"], args.model, result)
            verdict = result.get("verdict", "?")
            conf = result.get("confidence") or 0.0
            if not args.json:
                print(f"{verdict} ({conf:.2f})")
            results_log.append({
                "run_id": run["run_id"],
                "bug_id": bug_id,
                "arch": arch,
                "verdict": verdict,
                "confidence": conf,
            })
            ok += 1
        except Exception as exc:  # noqa: BLE001
            if not args.json:
                print(f"ERROR: {exc}")
            results_log.append({
                "run_id": run["run_id"],
                "bug_id": bug_id,
                "arch": arch,
                "verdict": "VALIDATION_ERROR",
                "error": str(exc),
            })
            errors += 1

    conn.close()

    if args.json:
        print(json.dumps({
            "status": "ok" if errors == 0 else "partial",
            "validated": ok,
            "errors": errors,
            "results": results_log,
        }))
    else:
        print(f"\nDone. {ok} validated, {errors} errors.")


def _fail(msg: str, args: argparse.Namespace) -> None:
    if getattr(args, "json", False):
        print(json.dumps({"status": "error", "message": msg}))
    else:
        print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
