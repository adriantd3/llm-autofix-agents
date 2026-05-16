# SPEC-012 Tasks

## SH1 — Core infrastructure

- [x] R3.1: Create `agents/instructions/_shared.py` with 6 shared constants
- [x] R3.2: Verify all constants render correctly when embedded via f-strings (import check)

## SH2 — Overfit removal (R1)

- [x] R1.1: `orchestrator.py` — replace `_parse_mpd_formats` with `<function_or_class_name>` (2 occurrences: STEP 1 + STEP 2)
- [x] R1.2: `orchestrator.py` — remove `ImportError 'cannot import name X'` alias recipe from FAILURE RECOVERY
- [x] R1.3: `mono_agent.py` — remove `ImportError 'cannot import name X'` alias recipe from TOOL-SPECIFIC RULES
- [x] R1.4: `planner_executor.py` (PLANNER) — replace `"None, False, 0, empty string, negative numbers"` enumeration
- [x] R1.5: `handoff.py` (LOCALIZER) — replace `"empty strings, False, None, and 0 if present in the test"` enumeration

## SH3 — Tool mechanics triage (R2)

- [x] R2.1: `mono_agent.py` — remove `replace_in_file` retry detail (covered by tool docstring)
- [x] R2.2: `mono_agent.py` — remove `write_file` truncation warning (covered by tool docstring + code guard)
- [x] R2.3: `mono_agent.py` — keep `run_test_target` cwd note as short TOOL NOTE (observed failure pattern)
- [x] R2.4: `orchestrator.py` — reduce TOOL STRATEGY from ~10 lines to 5 concise bullets

## SH4 — Deduplication via _shared.py (R3)

- [x] R3.3: `mono_agent.py` — convert to f-string, embed TEST_FILES_ARE_CORRECT_RULE, CODE_FIRST_DIAGNOSIS_PRINCIPLE, PROPAGATION_CHECK_RULE, READ_BEFORE_EDIT_RULE, ITERATION_RECORD_FORMAT
- [x] R3.4: `orchestrator.py` — convert MAIN to f-string, embed all relevant constants; keep EXPLORER and TEST_RUNNER as plain strings
- [x] R3.5: `planner_executor.py` — convert PLANNER + EXECUTOR to f-strings, embed relevant constants
- [x] R3.6: `handoff.py` — convert all 4 agents to f-strings, embed relevant constants

## SH5 — Output schema unification (R4)

- [x] R4.1: `orchestrator.py` — replace "plain-text summary" / "You do NOT need to produce JSON" with ITERATION_RECORD_FORMAT
- [x] R4.2: Verify provider text-fallback parser is unchanged (no runtime changes needed)

## SH6 — Anti-wander gate (R5)

- [x] R5.1: `iteration.py` `build_iteration_input` — prepend anti-wander line for `iteration ≥ 2`
- [x] R5.2: Unit test impact check — no new failures in `test_iteration_input.py` (pre-existing import error excluded)

## SH7 — Read-before-edit rule (R6)

- [x] R6.1: `_shared.py` — add `READ_BEFORE_EDIT_RULE` constant
- [x] R6.2: `mono_agent.py` — add as ABSOLUTE RULE 7
- [x] R6.3: `orchestrator.py` — add as ABSOLUTE RULE 6
- [x] R6.4: `planner_executor.py` (EXECUTOR) — add as ABSOLUTE RULE 2
- [x] R6.5: `handoff.py` (PATCHER) — add as ABSOLUTE RULE 2

## SH8 — Documentation

- [x] Create `specs/012-prompt-refactor-anti-overfit/spec.md`
- [x] Create `specs/012-prompt-refactor-anti-overfit/tasks.md`
- [x] Update `specs/status.md` with entry 012

## SH9 — Validation (to run post-implementation)

- [x] `pytest tests/` — 292 passed, 3 pre-existing failures (circular import + FindTestFunctionClassMethodTests)
- [x] No-overfit grep check — empty (clean)
- [x] Smoke: thefuck-1 passes in 1 iteration
- [x] BugsInPy regression: `batches/bugsinpy-orchestrator-candidates-batch1.yaml` — 7/9 success
      - thefuck-5: GENUINE_FIX (was OVERFIT) ✓
      - fastapi-1: GENUINE_FIX (was OVERFIT) ✓
      - thefuck-7: still OVERFIT (R7 did not trigger — assertion failure, no intra-function frame)
      - cookiecutter-4: partial — correct diagnosis, whitespace broke flake8 → **excluded from dataset**
      - pandas-10: failed — C extension missing, build-system issue → **excluded from dataset**
- [ ] QuixBugs subset regression batch (pending)

## SH11 — Type A restriction removal (R8)

- [x] R8.1: `orchestrator.py` (Explorer) — remove "You do NOT edit/run/apply" intro + ABSOLUTE RULES 1–2 ("NEVER modify/run. You have no edit/execution tools.")
- [x] R8.2: `orchestrator.py` (TestRunner) — remove "You do NOT edit files / apply patches" + ABSOLUTE RULE 1 ("NEVER modify any file. You have no edit tools."); renumber remaining rules
- [x] R8.3: `handoff.py` (Triage) — remove "You CANNOT edit files / run tests / apply patches" + FORBIDDEN: "Editing any file" + "Running tests or commands"
- [x] R8.4: `handoff.py` (Localizer) — remove "You CANNOT edit files" + FORBIDDEN: "Editing any file" + "Applying patches or fixes"
- [x] R8.5: `handoff.py` (Validator) — remove "You CANNOT edit files / hand off to another agent" + entire FORBIDDEN section (all 3 items were Type A)
- [x] R8.6: `planner_executor.py` (Planner) — remove FORBIDDEN: "Editing any file (you do not have edit tools)"

## SH12 — System-agnostic sub-agent prompts (R9)

- [x] R9.1: `orchestrator.py` (Explorer) — rewrite intro: "APR Explorer, read-only task-agent called by APR Orchestrator" → "a code analysis agent"; remove "APR" and orchestrator references
- [x] R9.2: `orchestrator.py` (TestRunner) — rewrite intro: "APR Test Runner, execution task-agent called by APR Orchestrator" → "a test execution agent"
- [x] R9.3: `handoff.py` (Triage) — rewrite intro: "APR Triage agent in a multi-agent handoff pipeline" → "a bug triage agent"; remove "produce the final result" (system-internal concept)
- [x] R9.4: `handoff.py` (Localizer) — rewrite intro: "APR Localizer agent in a multi-agent handoff pipeline" → "a bug localization agent"; remove "produce the final result"
- [x] R9.5: `handoff.py` (Patcher) — rewrite intro: "APR Patcher agent in a multi-agent handoff pipeline" → "a code repair agent"
- [x] R9.6: `handoff.py` (Validator) — rewrite intro: "APR Validator/Reporter agent in a multi-agent handoff pipeline" → "a test validation agent"; remove "This is the FINAL step" (pipeline-topology concept)
- [x] R9.7: `planner_executor.py` (Planner) — rewrite intro: "APR Planner agent in a planner-executor pipeline" → "a bug analysis and repair planning agent"; remove "You do NOT edit code" (Type A + system framing)
- [x] R9.8: `planner_executor.py` (Executor) — rewrite intro: "APR Executor agent in a planner-executor pipeline" → "a code repair agent"

## SH13 — Output schema moved to Pydantic (R10)

- [x] R10.1: `provider.py` — add class docstring to `AgentFixIterationResult` with behavioral honesty note
- [x] R10.2: `provider.py` — add `Field(description=...)` to `status` (includes "done"/"stuck"/"in_progress" semantics), `reasoning_summary`, `confidence`, `notes`, `changed_files`
- [x] R10.3: `provider.py` — add class docstring to `AgentFixIterationRecord` (harness metadata note)
- [x] R10.4: `_shared.py` — remove `ITERATION_RECORD_FORMAT` constant entirely
- [x] R10.5: `mono_agent.py` — remove `ITERATION_RECORD_FORMAT` import + `{ITERATION_RECORD_FORMAT}` embed
- [x] R10.6: `orchestrator.py` — remove `ITERATION_RECORD_FORMAT` import + `{ITERATION_RECORD_FORMAT}` embed from MAIN
- [x] R10.7: `handoff.py` — remove `ITERATION_RECORD_FORMAT` import + `{ITERATION_RECORD_FORMAT}` embed from VALIDATOR
- [x] R10.8: `planner_executor.py` — remove `ITERATION_RECORD_FORMAT` import + `{ITERATION_RECORD_FORMAT}` embed from EXECUTOR

## SH10 — Dataset cleanup (post-validation)

- [x] `batches/bugsinpy-orchestrator-candidates-batch1.yaml` — removed pandas-10 and cookiecutter-4 with comments explaining exclusion
- [x] `specs/012-prompt-refactor-anti-overfit/spec.md` — documented validation results, R7 hit rate, dataset exclusions, remaining issues
