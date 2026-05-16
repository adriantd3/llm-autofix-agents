---
name: apr-validator
description: 'Validate APR (Automated Program Repair) fixes formally. Use when running `autofix validate`, when evaluating if a generated patch is CORRECT/PLAUSIBLE/INCORRECT/INFRA_FAIL, when comparing agent patches against canonical ground truth, when assessing overfitting to tests, or when the user mentions "validar", "validate", "verdict", "formal validation", "fix quality".'
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

### Step 5 — Assess test signal

Evaluate the test exit code and output:
- Exit code 0 → tests passed
- Exit code ≠ 0 → check if failure is due to:
  - Bug still present (INCORRECT)
  - Infrastructure issue: missing deps, compilation error, timeout unrelated to bug code (INFRA_FAIL)

### Step 6 — Synthesize verdict

Apply the decision tree below and produce the final verdict with justification.

## Decision Tree

```
                    ┌─────────────────┐
                    │ test_exit_code=0?│
                    └────────┬────────┘
                      yes /     \ no
                         /       \
              ┌─────────▼──┐   ┌──▼──────────────┐
              │ canonical   │   │ infra failure?   │
              │ available?  │   │ (deps/compile/   │
              │             │   │  timeout)        │
              └──┬──────┬──┘   └──┬──────────┬───┘
              yes│      │no       │yes       │no
                 │      │         │          │
         ┌───────▼──┐   │    ┌───▼────┐  ┌──▼────────┐
         │semantically│  │    │INFRA_  │  │INCORRECT  │
         │matches?   │  │    │FAIL    │  │           │
         └──┬─────┬──┘  │    └────────┘  └───────────┘
         yes│     │no    │
            │     │      │
      ┌─────▼──┐ ┌▼─────────┐ ┌───────────┐
      │CORRECT │ │PLAUSIBLE  │ │CORRECT *  │
      └────────┘ └───────────┘ └───────────┘

  * Without canonical: CORRECT only if the fix logic is clearly
    sound and addresses the root cause visible in the traceback.
    If unsure, use PLAUSIBLE with lower confidence.
```

## Verdict Definitions

| Verdict | Meaning | Criteria |
|---------|---------|----------|
| **CORRECT** | Fix repairs the bug correctly | Tests pass AND same root cause as canonical (or clearly sound without canonical) |
| **PLAUSIBLE** | Fix makes tests pass but may overfit | Tests pass BUT different approach, partial fix, or overfits assertions |
| **INCORRECT** | Fix does not repair the bug | Tests fail for bug-related reasons, or logic is semantically wrong |
| **INFRA_FAIL** | Cannot evaluate due to infrastructure | Test failure from missing deps, compilation errors, timeouts unrelated to bug |

## Edge Cases

### No canonical patch available

- Set `patch_semantically_matches = null`
- Base verdict purely on test signal + semantic analysis of the patch
- Use CORRECT only if the logic is clearly sound; prefer PLAUSIBLE if uncertain
- Lower confidence (0.4–0.6 typical)

### Test timeout

- If timeout is due to infinite loop introduced by the patch → INCORRECT
- If timeout is due to environment/infra (slow CI, missing resource) → INFRA_FAIL

### Multi-file patches

- All changed files must be consistent with the fix intent
- Extra changes (formatting, imports not needed) don't disqualify but lower confidence
- If only some files are relevant and others are noise → PLAUSIBLE

### Patch is empty (no changes)

- If tests pass with no changes → investigate if test was already passing (INFRA_FAIL or PLAUSIBLE with note)
- If tests fail → INCORRECT

### Agent added workarounds

- `try/except` that silences the error → PLAUSIBLE (not addressing root cause)
- Hardcoded return values matching test assertions → PLAUSIBLE (overfitting)
- Proper logic fix → evaluate normally

## Structured Output

```json
{
  "verdict": "CORRECT | PLAUSIBLE | INCORRECT | INFRA_FAIL",
  "confidence": 0.85,
  "test_passed": true,
  "infra_fail_detected": false,
  "patch_semantically_matches": true,
  "justification": "Concise explanation of reasoning (2-4 sentences)"
}
```

## CLI Usage

```bash
# Validate all runs in a batch directory (uses batch.db)
uv run autofix validate --batch-dir results/batch-xxx/ \
  --canonical-root ~/Projects/BugsInPy \
  --model gpt-4.1-mini --provider openai

# Validate a single run
uv run autofix validate --db results/batch-xxx/batch.db \
  --run-id run-abc123 --canonical-root ~/Projects/QuixBugs

# Force re-validation + create analysis views
uv run autofix validate --batch-dir results/batch-xxx/ \
  --canonical-root ~/Projects/BugsInPy --force --create-views
```

## Confidence Guidelines

| Scenario | Typical confidence |
|----------|-------------------|
| Canonical available + clear semantic match | 0.85–0.95 |
| Canonical available + clear mismatch | 0.80–0.90 |
| No canonical + test passes + logic is sound | 0.50–0.70 |
| No canonical + test passes + unclear logic | 0.40–0.55 |
| INFRA_FAIL (clear env issue in logs) | 0.85–0.95 |
| Test fails + fix is obviously wrong | 0.90–0.95 |
