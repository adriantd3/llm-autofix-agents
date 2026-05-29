---
name: apr-validator
description: 'Validate APR (Automated Program Repair) fixes formally. Use when running `autofix validate`, when evaluating if a generated patch is CORRECT/PLAUSIBLE/OVERFITTING/FAIL, when comparing agent patches against canonical ground truth, when assessing overfitting to tests, or when the user mentions "validar", "validate", "verdict", "formal validation", "fix quality".'
---

# APR Validator — Formal Fix Validation

Validate whether a generated fix is semantically correct by comparing it against the canonical patch, analyzing the test signal, and producing a structured verdict.

## When to Use

- Validating batch results after an APR run
- Evaluating individual fixes for correctness vs test-overfitting
- Producing formal verdicts for TFM comparative analysis
- Debugging false positives (tests pass but fix is wrong)

## Inputs Required

The validator needs access to these artefacts for each run:

| Input | Source | Required |
|-------|--------|----------|
| Generated patch (diff) | `runs.diff_path` → file on disk | Yes |
| Test exit code | `iterations.test_exit_code` (last iteration) | Yes |
| Test output (tail) | `runs.live_log_path` → file on disk | Yes |
| Canonical patch | BugsInPy/QuixBugs repo on disk | Recommended |
| Problem ID | `runs.problem_id` (e.g. `httpie-1`, `gcd`) | Yes |
| Dataset type | Inferred from `runs.benchmark_name` | Yes |

## Canonical Patch Resolution

### QuixBugs

Root: cloned QuixBugs repo.
Path: `correct_python_programs/{bug_id}.py`

### BugsInPy

Root: cloned BugsInPy repo (e.g. `~/Projects/BugsInPy`).
Path: `projects/{project}/bugs/{number}/bug_patch.txt`

The `problem_id` format is `{project}-{number}` where project may contain hyphens.
Resolution: split on last hyphen → `youtube-dl-1` → project=`youtube-dl`, number=`1`.

If the BugsInPy repo is not available locally, use [./scripts/fetch_bugsinpy_patch.sh](./scripts/fetch_bugsinpy_patch.sh) to download a specific patch from GitHub.

## Validation Protocol (6 Steps)

Follow this protocol **exactly in order** for each run:

### Step 1 — Understand the bug context

Read the problem_id and dataset to understand what project and function is involved.
If possible, review the test file and error traceback from the live log to understand what the test expects.

### Step 2 — Analyze the generated patch

Read the agent's diff. Identify:
- What files were changed
- What logic was modified
- Does the change make sense independently of the test?

### Step 3 — Analyze the canonical patch (if available)

Read the ground-truth developer fix. Identify:
- What root cause did the developer address?
- What was the minimal correct change?

### Step 4 — Semantic comparison

Compare the two patches semantically (NOT line-by-line):
- Do they address the **same root cause**?
- Is the generated patch a valid alternative approach to the same fix?
- Or does it address a different aspect / overfit to test assertions?

Set `patch_semantically_matches`:
- `true`: same root cause, equivalent fix (even if code differs)
- `false`: different approach, addresses different issue, or overfits
- `null`: canonical patch not available

### Step 5 — Detect overfitting

Only runs with `test_exit_code=0` reach this step (validator is not called for failed runs).
Check whether the agent gamed the tests rather than fixing the root cause:
- Hardcoded return values matching test assertions → OVERFITTING
- Modified the test file itself → OVERFITTING
- `try/except` silencing the error without fixing the logic → lean OVERFITTING
- Exit code ≠ 0 in the log (edge case: re-run discrepancy) → flag in justification

### Step 6 — Synthesize verdict

Apply the decision tree below and produce the final verdict with justification.

## Decision Tree

```
                    ┌─────────────────────┐
                    │ tests_exit_code = 0  │  (only success runs reach here)
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ overfitting signal?  │
                    └──────┬──────────┬───┘
                        yes│          │no
                           │          │
               ┌───────────▼──┐  ┌───▼──────────────┐
               │ OVERFITTING  │  │ canonical patch    │
               └──────────────┘  │ available?        │
                                 └───┬───────────┬───┘
                                  yes│           │no
                                     │           │
                            ┌────────▼──┐  ┌────▼──────────┐
                            │semantically│  │ CORRECT *      │
                            │matches?   │  │ or PLAUSIBLE   │
                            └──┬─────┬──┘  └────────────────┘
                            yes│     │no
                               │     │
                         ┌─────▼──┐ ┌▼──────────┐
                         │CORRECT │ │ PLAUSIBLE  │
                         └────────┘ └────────────┘

  * Without canonical: CORRECT only if the fix logic is clearly
    sound and addresses the root cause visible in the traceback.
    If unsure, use PLAUSIBLE with lower confidence.
```

## Verdict Definitions

| Verdict | Meaning | Criteria |
|---------|---------|----------|
| **CORRECT** | Fix repairs the bug correctly | Tests pass AND same root cause as canonical (or clearly sound without canonical) |
| **PLAUSIBLE** | Fix works but is incomplete or diverges | Tests pass BUT different approach, partial fix, or misses propagation |
| **OVERFITTING** | Fix games the tests | Tests pass BUT agent modified tests, hardcoded values, or special-cased inputs |
| **FAIL** | No accepted fix | Tests did not pass, no patch is available, or semantic validation is not applicable |

## Edge Cases

### No canonical patch available

- Set `patch_semantically_matches = null`
- Base verdict purely on semantic analysis of the patch against the traceback and tests
- Use CORRECT only if the logic is clearly sound; prefer PLAUSIBLE if uncertain
- Lower confidence (0.4–0.6 typical)

### Multi-file patches

- All changed files must be consistent with the fix intent
- Extra changes (formatting, imports not needed) don’t disqualify but lower confidence
- If only some files are relevant and others are noise → PLAUSIBLE

### Patch is empty (no changes)

- If tests pass with no changes → investigate if the test was already passing before the agent ran; note in justification—likely PLAUSIBLE with low confidence

### Agent added workarounds

- `try/except` that silences the error → PLAUSIBLE (not addressing root cause)
- Hardcoded return values matching test assertions → OVERFITTING
- Proper logic fix → evaluate normally

## Structured Output

```json
{
  "verdict": "CORRECT | PLAUSIBLE | OVERFITTING | FAIL",
  "confidence": 0.85,
  "test_passed": true,
  "patch_semantically_matches": true,
  "justification": "Concise explanation of reasoning (2-4 sentences)"
}
```

## Agent Step 7 — Persist Verdicts to DB

After producing verdicts (Steps 1–6), write them to the batch DB using
[./scripts/validate_batch.py](./scripts/validate_batch.py).
**Do not skip this step** — verdicts that exist only in the chat are not persisted.

The script is a pure persistence layer. **The agent is the judge.** The script
does not call any LLM; it only writes the verdicts you provide.

### When to run

- After completing validation of one or more runs in a batch
- After a full batch run completes and you want to validate all resolved runs at once
- Any time the user asks to "persist", "guardar" or "almacenar" validation results

### Two-step workflow

**Step 7a — Discover pending runs:**

```bash
uv run python .agents/skills/apr-validator/scripts/validate_batch.py \
  --db <path-to-batch.db> --list-runs
```

Returns a JSON array of runs needing validation. Each entry contains:
`run_id`, `target_repo`, `live_log_path`, `problem_id`, `arch`, `benchmark_name`.
Use these fields to locate patch files and canonical programs for steps 1–6.

```bash
# Include already-validated runs (re-validation)
uv run python .agents/skills/apr-validator/scripts/validate_batch.py \
  --db <path-to-batch.db> --list-runs --force

# Discover a specific run only
uv run python .agents/skills/apr-validator/scripts/validate_batch.py \
  --db <path-to-batch.db> --list-runs --run-id <run_id>
```

**Step 7b — Produce verdicts (steps 1–6)** for each run returned above.

**Step 7c — Persist all verdicts in one call:**

```bash
echo '<json-array-of-verdicts>' | \
uv run python .agents/skills/apr-validator/scripts/validate_batch.py \
  --db <path-to-batch.db>
```

Each element of the JSON array must have:

| Field | Type | Required |
|-------|------|----------|
| `run_id` | string | Yes |
| `verdict` | `CORRECT\|PLAUSIBLE\|OVERFITTING\|FAIL` | Yes |
| `confidence` | float 0.0–1.0 | Yes |
| `test_passed` | bool | Yes |
| `patch_semantically_matches` | bool or null | Yes |
| `justification` | string | Yes |

The script prints a JSON confirmation:

```json
{"status": "ok", "written": 12, "errors": 0, "results": [
  {"run_id": "run-...", "verdict": "CORRECT", "confidence": 0.92},
  ...
]}
```

Exit code `0` = success (even with partial errors). Check `"status"`: `"ok"` or `"partial"`.

The script is **idempotent**: each run produces exactly one row in `run_validations`
(`INSERT OR REPLACE`). Re-running with the same `run_id` overwrites the previous verdict.

## Confidence Guidelines

| Scenario | Typical confidence |
|----------|-------------------|
| Canonical available + clear semantic match | 0.85–0.95 |
| Canonical available + clear mismatch | 0.80–0.90 |
| No canonical + test passes + logic is sound | 0.50–0.70 |
| No canonical + test passes + unclear logic | 0.40–0.55 |
| OVERFITTING (clear evidence of test-gaming) | 0.85–0.95 |

## Fallback (MANDATORY): When validate_batch.py Fails

**If validate_batch.py fails for any reason (import error, exception, non-zero exit, tool unavailable), do NOT stop. Perform both steps directly using Python + sqlite3. This is NOT optional.**

### Fallback 7a — Discover runs manually

```python
import sqlite3, json
from pathlib import Path

db_path = Path("<path-to-batch.db>")
repo_root = db_path.resolve().parent.parent.parent   # results/batch-name/batch.db → REPO_ROOT

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
rows = conn.execute("""
    SELECT r.run_id, r.target_repo, r.live_log_path, r.diff_path,
           r.benchmark_name, r.problem_id, a.name AS arch
    FROM runs r
    JOIN architectures a ON a.architecture_id = r.architecture_id
    WHERE r.resolved = 1
      AND r.live_log_path IS NOT NULL
      -- Remove the line below to force re-validation of already-validated runs:
      -- AND r.run_id NOT IN (SELECT run_id FROM run_validations)
""").fetchall()

def resolve(path, repo_root):
    if path and path.startswith("/results/"):
        return str(repo_root / "results" / path[len("/results/"):])
    return path

runs = []
for row in rows:
    r = dict(row)
    r["live_log_path"] = resolve(r["live_log_path"], repo_root)
    runs.append(r)

conn.close()
print(json.dumps(runs, indent=2))
```

### Fallback 7c — Persist verdicts manually

After producing verdicts following steps 1–6, write them to the DB directly:

```python
import sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path

db_path = Path("<path-to-batch.db>")
conn = sqlite3.connect(db_path)

verdicts = [
    # Fill in your verdicts here (one dict per run):
    {
        "run_id": "run-...",
      "verdict": "CORRECT",          # CORRECT | PLAUSIBLE | OVERFITTING | FAIL
        "confidence": 0.9,
        "test_passed": True,
        "patch_semantically_matches": True,   # True | False | None
        "justification": "...",
    },
    # ...
]

for v in verdicts:
    pm_raw = v.get("patch_semantically_matches")
    patch_matches = 1 if pm_raw is True else (0 if pm_raw is False else None)
  conn.execute("DELETE FROM run_validations WHERE run_id = ?", (v["run_id"],))
    conn.execute("""
        INSERT OR REPLACE INTO run_validations
            (validation_id, run_id, validated_at, validator_model,
             test_passed, infra_fail_detected, canonical_patch_available,
             patch_semantically_matches, verdict, confidence, justification)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(uuid.uuid4()),
        v["run_id"],
        datetime.now(timezone.utc).isoformat(),
        v.get("validator_model") or "claude-sonnet-4.5",
        1 if v.get("test_passed", True) else 0,
        0,
        1 if pm_raw is not None else 0,
        patch_matches,
        v["verdict"],
        v.get("confidence"),
        v.get("justification", ""),
    ))

conn.commit()
conn.close()
print(f"Written {len(verdicts)} verdicts.")
```
