---
name: apr-validator
description: 'Validate APR (Automated Program Repair) fixes formally. Use when running `autofix validate`, when evaluating if a generated patch is CORRECT/PLAUSIBLE/OVERFITTING/VALIDATION_ERROR, when comparing agent patches against canonical ground truth, when assessing overfitting to tests, or when the user mentions "validar", "validate", "verdict", "formal validation", "fix quality".'
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
| **VALIDATION_ERROR** | Pipeline error | Reserved — not produced by the LLM |

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
  "verdict": "CORRECT | PLAUSIBLE | OVERFITTING | VALIDATION_ERROR",
  "confidence": 0.85,
  "test_passed": true,
  "patch_semantically_matches": true,
  "justification": "Concise explanation of reasoning (2-4 sentences)"
}
```

## Agent Step 7 — Persist Verdicts to DB

After producing verdicts (Steps 1–6), run [./scripts/validate_batch.py](./scripts/validate_batch.py)
to write all results into the batch's `run_validations` table in a single command.
**Do not skip this step** — verdicts that exist only in the chat are not persisted.

### When to run

- After completing manual validation of one or more runs in a batch
- After a full batch run completes and you want to validate all resolved runs at once
- Any time the user asks to "persist", "guardar" or "almacenar" validation results

### Command

```bash
# Standard: validate all unvalidated resolved runs, get JSON summary
uv run python .agents/skills/apr-validator/scripts/validate_batch.py \
  --db <path-to-batch.db> --json

# Re-validate a single run (e.g. after correcting reasoning)
uv run python .agents/skills/apr-validator/scripts/validate_batch.py \
  --db <path-to-batch.db> --run-id <run_id> --force --json

# Force re-validation of everything in a batch
uv run python .agents/skills/apr-validator/scripts/validate_batch.py \
  --db <path-to-batch.db> --force --json

# Different judge model
uv run python .agents/skills/apr-validator/scripts/validate_batch.py \
  --db <path-to-batch.db> --model gpt-4o --json
```

Always pass `--json` when invoking from agent context — it emits a single JSON line
on stdout that you can read to confirm what was written:

```json
{"status": "ok", "validated": 12, "errors": 0, "results": [
  {"run_id": "run-...", "bug_id": "gcd", "arch": "mono_agent", "verdict": "CORRECT", "confidence": 0.92},
  ...
]}
```

Exit code `0` = success (even with partial errors). Check `"status"` field: `"ok"` or `"partial"`.

### What the script resolves automatically

| Field | Source |
|-------|--------|
| Generated patch | `it*.patch` files in the run directory (derived from `live_log_path`) |
| Bug identifier | Last path segment of `target_repo` |
| Dataset type | Detected from `target_repo` path (`quixbug` → QuixBugs, else BugsInPy) |
| Canonical program (QuixBugs) | `{target_repo}/correct_python_programs/{bug_id}.py` |
| Canonical program (BugsInPy) | Not yet supported — `patch_semantically_matches` will be `null` |
| Workspace root | Defaults to repo root (4 levels above the script); override with `--workspace-root` |

The script is **idempotent**: skips already-validated runs unless `--force` is passed.
Each run produces exactly one row in `run_validations` (`INSERT OR REPLACE`).

## Confidence Guidelines

| Scenario | Typical confidence |
|----------|-------------------|
| Canonical available + clear semantic match | 0.85–0.95 |
| Canonical available + clear mismatch | 0.80–0.90 |
| No canonical + test passes + logic is sound | 0.50–0.70 |
| No canonical + test passes + unclear logic | 0.40–0.55 |
| OVERFITTING (clear evidence of test-gaming) | 0.85–0.95 |
