# SPEC-012: Prompt Refactor — Anti-Overfit & Harness Hardening

## Context

After the first round of APR prompt improvements (code-first diagnosis, propagation check,
test-as-evidence framing), a batch of 9 BugsInPy bugs was validated with `qwen3.5:9b` +
`multi_agent_orchestrator`. 8/9 passed tests, but manual inspection of 4 cases (thefuck-5/7,
cookiecutter-4, fastapi-1) revealed **plausible-but-incorrect patches**: fixes that made the
failing test pass without restoring the correct intended behavior of the function. This is the
canonical APR failure mode known as "test overfitting" [REF-5, REF-6].

A deeper audit of all 10 system prompts against agent harness literature [REF-1, REF-2, REF-3,
REF-4, REF-7, REF-8, REF-9] revealed the following categories of problem:

1. **Overfit to specific dataset bugs** — literal symbols (`_parse_mpd_formats` from youtube-dl,
   `ImportError: cannot import name X` from `fix_xml_ampersands`) appeared verbatim in prompts,
   biasing the model toward those patterns on other bugs.

2. **Tool mechanics duplicated in system prompts** — rules already present in tool docstrings
   (`replace_in_file` retry, `write_file` truncation guard, `run_test_target` cwd) were repeated
   in the prompts, wasting tokens and diluting the critical rules. [REF-1]: *"We spent more time
   optimizing tools than the prompt. Document tools like a docstring for a junior dev."*

3. **Core rules scattered across 4–6 files** — "test files are correct", "code-first diagnosis",
   "propagation check", the JSON handoff schema, and the `AgentFixIterationRecord` schema were
   copy-pasted with micro-divergences, making consistent updates error-prone.

4. **Anti-wander absent** — the model could repeat near-identical attempts across iterations
   with no friction. [REF-1, REF-2] recommend an explicit stopping condition: "if your plan is
   the same as last time, report stuck."

5. **"MUST read before edit" not a hard rule** — [REF-2] (Cursor) elevates this to an ABSOLUTE
   RULE. The system prompts implied it but did not enforce it.

6. **Prompt-only code-first framing is insufficient** — `CODE_FIRST_DIAGNOSIS_PRINCIPLE` as a
   system prompt instruction competes against **position bias** [REF-10]: models attend more to
   content that appears early in the prompt. The failing test output always appears first, so the
   model implicitly patterns off the test before reading any source. The correct fix is structural:
   inject the source function into the prompt so it appears before the test function, establishing
   the semantic contract at the position where the model attends most. This mirrors the approach of
   SWE-agent [REF-3] (FileCommunicator), AutoCodeRover [REF-7] (fault localization before repair),
   and Agentless [REF-8] (explicit localization phase before patch generation).

All changes target **qwen3.5:9b** and **qwen3-coder:30b** as primary models — small and modern,
but with limited ability to follow abstract meta-instructions [REF-9]. Every rule added must be:
- A single concrete imperative (binary pass/fail for the model)
- Not relying on multi-sentence reasoning before a tool call
- Token-neutral or better vs. what it replaces

See also: `specs/lessons.md` (entry 2026-05-14 — sobreajuste a los tests).

## Goals

| ID | Change | Scope |
|----|--------|-------|
| R1 | Remove dataset-specific overfit examples from all prompts | orchestrator, mono_agent, planner_executor, handoff |
| R2 | Remove tool mechanics from system prompts that are covered by tool docstrings | mono_agent, orchestrator |
| R3 | Deduplicate shared rules into `agents/instructions/_shared.py` | all 4 instruction files |
| R4 | Unify output schema to `AgentFixIterationRecord` JSON in all final agents | orchestrator (was plain text) |
| R5 | Add anti-wander gate for iterations N≥2 | `flow/policies/iteration.py` |
| R6 | Add "never edit without reading" as ABSOLUTE RULE in all edit-capable agents | mono_agent, orchestrator, executor, patcher |
| R7 | Inject source function under test into first-iteration prompt, before the test function | `flow/policies/iteration.py` |

## Design

### `agents/instructions/_shared.py` (new)

Single source of truth for 6 constants. All prompt modules import and embed via f-strings.
No logic — only string constants.

| Constant | Canonical owner | Used in |
|----------|----------------|---------|
| `TEST_FILES_ARE_CORRECT_RULE` | `_shared.py` | mono_agent, orchestrator, executor, patcher |
| `CODE_FIRST_DIAGNOSIS_PRINCIPLE` | `_shared.py` | mono_agent, orchestrator, planner, localizer |
| `PROPAGATION_CHECK_RULE` | `_shared.py` | mono_agent, orchestrator, executor, patcher |
| `READ_BEFORE_EDIT_RULE` | `_shared.py` | mono_agent, orchestrator, executor, patcher |
| `HANDOFF_PAYLOAD_FORMAT` | `_shared.py` | triage, localizer, patcher, planner |
| `ITERATION_RECORD_FORMAT` | `_shared.py` | mono_agent, orchestrator, executor, validator |

Each prompt module is converted from a plain string literal to an `f"""..."""` that embeds the
relevant constants with `{CONSTANT_NAME}`.

### R1 — Overfit removal

Problem: prompts contained literal symbols derived from specific dataset bugs [REF-5, REF-6].
When the model sees `_parse_mpd_formats` as an example, it is more likely to apply the same
"search for this exact function pattern" heuristic on unrelated bugs.

- `orchestrator.py`: `"def _parse_mpd_formats"` (youtube-dl symbol) → `"<function_or_class_name>"`
  in STEP 1 and STEP 2 examples.
- `orchestrator.py`: `ImportError 'cannot import name X'` alias recipe → removed from FAILURE RECOVERY.
- `mono_agent.py`: same `ImportError` alias recipe block → removed from TOOL-SPECIFIC RULES.
- `planner_executor.py` (PLANNER): `"Consider ALL inputs: None, False, 0, empty string, negative numbers"`
  → `"consider the boundary inputs that the test actually exercises"`. The enumeration was derived
  from QuixBugs-style algorithmic bugs; it misled the model on BugsInPy real-world bugs.
- `handoff.py` (LOCALIZER): `"Include edge cases with empty strings, False, None, and 0 if present in the test"`
  → `"Consider the boundary inputs the test actually exercises"`.

### R2 — Tool mechanics triage (conservative for small models)

Problem: rules duplicated in both the system prompt and the tool docstring dilute the signal of
the critical rules [REF-1]. However, small models (qwen3.5:9b) often skip reading detailed tool
descriptions, so removal must be conservative.

Decision rule: only remove a mechanic if (a) it is literally present in the tool docstring AND
(b) we have not observed the model violating it in recent runs. Otherwise keep it in the prompt.

- `mono_agent.py`: removed `replace_in_file` retry details (covered by tool docstring) and
  `write_file` truncation warning (covered by tool docstring + code-level guard added 2026-05-13).
  Kept `run_test_target` cwd note (model violates this frequently) as a short TOOL NOTE.
- `orchestrator.py`: reduced `TOOL STRATEGY` section from ~10 lines to 5 concise bullets.

### R3 — Deduplication via `_shared.py`

Problem: DRY violation across 4 prompt files. A change to any shared rule required manual updates
in 4–6 locations, which already produced micro-divergences in the `PROPAGATION_CHECK_RULE` text.

Solution: extract into `_shared.py`. Owner is unambiguous; future updates touch one file.
No behavior change — models see the same text, just compiled from one place.

### R4 — Unified output schema

`ORCHESTRATOR_V2_MAIN_INSTRUCTIONS` previously instructed the agent to write a "plain-text
summary" and explicitly said "You do NOT need to produce JSON". This asymmetry with the other
3 final agents (mono_agent, executor, validator — all requesting `AgentFixIterationRecord`) was
unjustified. Unified to `ITERATION_RECORD_FORMAT`. The provider already has a text-fallback
parser — no runtime changes needed.

### R5 — Anti-wander gate

Problem: no friction preventing the model from repeating an identical or near-identical fix
attempt across iterations. `is_no_progress` in the iteration policy detects this post-hoc, but
the model already burned a full iteration before being stopped.

Solution [REF-1, REF-2]: inject an explicit gate at the start of every iteration N≥2:

> "This is attempt N/M. Your previous attempt failed. If your plan for this attempt is the same
> as before, stop now and report status='stuck'. Otherwise, your first action must be different
> from what you tried last time."

Phrased as an **action gate** (first action must differ) rather than a meta-reflection request
("state in 1 sentence what changes"). The latter causes small models to generate a prose sentence
that wastes tokens without constraining behavior. The former is binary and verifiable by the model.

### R6 — Read-before-edit as ABSOLUTE RULE

Problem: the `replace_in_file` retry loop that causes `old_text_not_found` errors is almost
always triggered by the model editing code it never read in the current turn. Making this an
explicit ABSOLUTE RULE [REF-2] eliminates the ambiguity.

Added to all edit-capable agents via `READ_BEFORE_EDIT_RULE`:
> "Never edit a file you have not read in this iteration. Always call read_file before
> replace_in_file / replace_lines / write_file."

Short, binary, model-verifiable.

### R7 — Source function injection into first-iteration prompt

**Why prompt instructions alone are insufficient for code-first diagnosis:**

`CODE_FIRST_DIAGNOSIS_PRINCIPLE` (added in the previous round) is a system prompt instruction
asking the model to "read the source before analyzing the test". In practice, the first-iteration
prompt structure was:

```
[FAILURE_DRIVEN_INTRO]
[Focused test command]
[Failing test execution output]      ← test-first
[Failing test function body]         ← test-first
```

The model processes tokens sequentially. Content appearing early in the prompt has
disproportionate influence on the model's subsequent reasoning — the "position bias" or "lost
in the middle" phenomenon [REF-10]. A system-prompt instruction to "read source first" cannot
overcome a user-message layout that puts test evidence first.

**Solution: structural injection before the test function.**

`_build_first_iteration_input` now calls `_extract_source_function_under_test` and injects the
result before `_extract_failing_test_function`:

```
[FAILURE_DRIVEN_INTRO]
[Focused test command]
[Failing test execution output]
[Source function under test]   ← NEW: appears before the test, leverages position bias
[Failing test function body]   ← unchanged
```

The source function block header reinforces the framing:
> "--- Source function under test (defines the CORRECT behavior — understand this BEFORE reading the test) ---"

**Implementation: `_extract_source_function_under_test`**

Walks all Python traceback frames (`File "...", line N, in func_name`) from innermost (closest
to the AssertionError) to outermost. Skips:
- Test files (paths matching test/ / tests/ / test_*.py / *_test.py)
- Synthetic frames (`<module>`, `<lambda>`, `<listcomp>`, etc.)
- Paths that don't resolve under `repo_root` (stdlib, site-packages)

Returns the first matching source function, extracted via `_extract_raw_function`, formatted with
the source-specific header. Truncates at 3000 chars (same limit as test function extraction).

**Why this addresses the overfitting problem:**

The 4 plausible-but-incorrect patches (thefuck-5/7, cookiecutter-4, fastapi-1) shared a common
pattern: the model saw the test assertion first, found the minimal code change to satisfy it,
and never understood what the function was supposed to do more broadly. With the source function
visible first, the model has the function's full semantic context (type handling, edge case
branches, return conditions) before it sees what the test expects. This mirrors:

- **SWE-agent** [REF-3]: `FileCommunicator` keeps a persistent "file view" so the agent always
  has source context alongside the error. Source injection approximates this for the first iteration.
- **AutoCodeRover** [REF-7]: explicit fault localization step retrieves the suspicious method
  before generating a patch. Source injection front-loads this result without requiring an extra
  agent turn.
- **Agentless** [REF-8]: two-phase pipeline — localize (find suspicious functions), then repair.
  Source injection embeds the localization result directly in the repair prompt.

**Limitations:**

- Only works for Python tracebacks (pytest format). Non-Python datasets would need a different
  extractor (R9, deferred).
- If the traceback does not name the source function (e.g. import-time errors), injection falls
  back to empty string — the test-only prompt is used unchanged.
- Does not help when the bug is in a function not named in the traceback (rare in BugsInPy).

### R8 — Remove Type A capability restrictions from sub-agent prompts

**Problem:** Several sub-agent system prompts included explicit capability-restriction instructions
for actions the agent is structurally incapable of performing because the harness never assigns it
those tools. Examples:

- Explorer: *"You do NOT edit files. NEVER modify any file. You have no edit tools."*
  → `APR_ORCHESTRATOR_EXPLORER_TOOLS` contains no write/replace tools.
- TestRunner: *"You do NOT edit files. You do NOT apply patches. You have no edit tools."*
  → `APR_ORCHESTRATOR_TEST_RUNNER_TOOLS` contains no write/replace tools.
- Triage, Localizer: *"You CANNOT edit files (you do not have edit tools)."*
  → `APR_TRIAGE_TOOLS` and `APR_LOCALIZER_TOOLS` contain no write/replace tools.
- Validator: *"You CANNOT edit files. You CANNOT hand off to another agent."*
  → `APR_VALIDATOR_TOOLS` and `APR_LOCALIZER_TOOLS` contain no edit or handoff tools.
- Planner: *"You do NOT edit code. Editing any file (you do not have edit tools)."*
  → `APR_PLANNER_TOOLS` contains no write/replace tools.

These instructions add token cost without information value, and may cause over-cautious
behavior (the model hedging around adjacent actions it also cannot take). The enforcement is
structural (harness tool assignment), not behavioral (model instruction).

**Decision rule:** Remove any instruction of the form *"You cannot/do not X"* when X requires a
tool that is absent from the agent's tool profile. Retain restrictions on actions the agent
*could* attempt with its available tools (e.g., "do not run inline Python scripts via
`execute_command`" when `execute_command` is in the profile).

**Scope:** Explorer, TestRunner, Triage, Localizer, Validator, Planner.
Patcher and Executor are unaffected (they have edit tools).

### R9 — System-agnostic sub-agent prompts

**Problem:** Sub-agent system prompts were written with awareness of the broader APR pipeline:
they referenced "APR", "multi-agent handoff pipeline", "planner-executor pipeline", "iteration
record", and their position in the orchestration hierarchy. This context is irrelevant to the
sub-agent's actual task and pollutes its context window with information it doesn't need.

A sub-agent called to *read code and answer a question* does not need to know it is part of an
APR system or that there are "iteration records" at all. That framing biases the agent toward
APR-specific reasoning patterns when it should be operating as a generic code analysis tool.

**Design principle:** Sub-agents should be described purely by **what they do**, not by what
system they belong to or what they are not. The orchestrator/main agent holds the system context;
the sub-agent receives a task and returns a result.

**Changes applied:**

| Agent | Before | After |
|-------|--------|-------|
| Explorer | "APR Explorer, a read-only task-agent called by the APR Orchestrator" | "a code analysis agent" |
| TestRunner | "APR Test Runner, an execution task-agent called by the APR Orchestrator" | "a test execution agent" |
| Triage | "APR Triage agent in a multi-agent handoff pipeline" | "a bug triage agent" |
| Localizer | "APR Localizer agent in a multi-agent handoff pipeline" | "a bug localization agent" |
| Patcher | "APR Patcher agent in a multi-agent handoff pipeline" | "a code repair agent" |
| Validator | "APR Validator/Reporter agent in a multi-agent handoff pipeline" | "a test validation agent" |
| Planner | "APR Planner agent in a planner-executor pipeline" | "a bug analysis and repair planning agent" |
| Executor | "APR Executor agent in a planner-executor pipeline" | "a code repair agent" |

References to "iteration record", "final iteration record", and handoff pipeline topology were
removed from all sub-agent prompts. Main agents (mono_agent, orchestrator main) retain full
APR context as they coordinate the overall repair loop.

### R10 — Output schema field semantics moved to Pydantic

**Problem:** `ITERATION_RECORD_FORMAT` in `_shared.py` duplicated the field-level schema of
`AgentFixIterationRecord` as free text in the system prompt. The OpenAI Agents SDK serializes
the Pydantic model's JSON schema and passes it to the model as `output_type` — including class
docstrings (`description` key) and `Field(description=...)` per property. The system prompt
description was therefore redundant.

**Evidence (from SDK inspection):**
```python
AgentOutputSchema(ExampleModel, strict_json_schema=False)
# → _output_schema includes:
#   "description": <class docstring>
#   "properties": { "field": { "description": <Field(description=...)> } }
```

**Changes:**

1. `AgentFixIterationResult` — added class docstring + `Field(description=...)` for
   `status`, `reasoning_summary`, `confidence`, `notes`. The `status` description includes the
   full semantics of each value ("done", "stuck", "in_progress").
2. `AgentFixIterationRecord` — added class docstring. `changed_files` gets a description;
   harness-populated fields (`input_tokens`, `output_tokens`, `total_tokens`, `last_agent_name`)
   are left without description to avoid confusing the agent.
3. `ITERATION_RECORD_FORMAT` removed entirely from `_shared.py` — the per-field listing is now
   in the schema. The behavioral guidance ("done only when tests pass", "be honest") is already
   covered by the WHEN TO STOP and Completion criteria sections in each main agent's workflow.
4. All four final-agent prompts (mono_agent, orchestrator main, executor, validator) drop the
   `{ITERATION_RECORD_FORMAT}` embed and the import.

## Out of scope (deferred)

| ID | Why deferred |
|----|-------------|
| R8-FEWSHOT | Few-shot demos for small models — needs A/B with token cost metrics before adopting [REF-9] |
| R9-INTRO | Audit `_FAILURE_DRIVEN_INTRO` ↔ system prompt overlap — mechanical but requires deciding owner per rule |
| R10-PYTEST | Decouple `_extract_failing_test_function` from pytest/Python — not urgent, all current datasets are Python |

## Validation

1. **Unit tests**: `pytest tests/` — no new failures vs baseline (pre-existing: 3 failures
   from circular import and `FindTestFunctionClassMethodTests`).
2. **No-overfit check**: `grep -rE "(_parse_mpd|fix_xml|cannot import name X|None, False, 0)" src/llm_autofix_agents/agents/instructions/` → empty.
3. **Smoke**: `batches/bugsinpy-test-thefuck1.yaml` — thefuck-1 must still resolve.
4. **BugsInPy regression**: re-run `batches/bugsinpy-orchestrator-candidates-batch1.yaml` (9 bugs).
   Must solve ≥8. Observe whether previously-overfitting bugs (thefuck-5/7, cookiecutter-4,
   fastapi-1) now produce more semantically correct patches.
5. **QuixBugs regression**: run a subset (5-10 bugs) to detect regressions in multi-assert bugs
   after removing the `None/False/0` enumeration (R1).
6. **Source injection smoke**: manually inspect `events.jsonl` for one run — confirm the source
   function block appears in the first iteration's `facade_input` event, before the test function.
7. **Small-model sanity**: each modified prompt is scannable in one pass; no rule added requires
   >1 sentence of reasoning; total token count ≤ pre-refactor for prompts where R2/R1 removed text.

## Validation results (2026-05-15)

Batch run: `results/batch-bugsinpy-orchestrator-candidates-batch1-20260515T170452Z`
Model: qwen3.5:9b + multi_agent_orchestrator, max_iterations=3.

### Summary: 7/9 success (vs. 8/9 previously with 4 overfit patches)

| Bug | Before SPEC-012 | After SPEC-012 | Change |
|-----|-----------------|----------------|--------|
| thefuck-1 | pass | pass | = |
| thefuck-2 | pass | pass | = |
| **thefuck-5** | pass (OVERFIT) | pass (**GENUINE_FIX**) | ✓ improved |
| thefuck-6 | pass | pass | = |
| **thefuck-7** | pass (OVERFIT) | pass (**OVERFIT**) | ✗ unchanged |
| tornado-9 | pass | pass | = |
| **fastapi-1** | pass (OVERFIT) | pass (**GENUINE_FIX**) | ✓ improved |
| **cookiecutter-4** | pass (OVERFIT) | partial | ~ improved diagnosis, excluded (see below) |
| pandas-10 | timeout | failed | excluded (see below) |

### Anti-overfit results

**thefuck-5 — GENUINE_FIX ✓**: Agent identified that `git_push.py:match()` produced false positives
when Bitbucket push output contained "set-upstream" as a substring (successful push, not an error).
Applied a guard clause excluding outputs with `remote:` + PR-creation indicators. Semantically correct;
not hardcoded to test strings.

**fastapi-1 — GENUINE_FIX ✓**: Agent added `exclude_defaults: bool = False` to `jsonable_encoder()`
and threaded it through all four internal code paths following the existing `exclude_unset` pattern.
Complete propagation; not a minimal test-satisfying hack.

**thefuck-7 — OVERFIT ✗**: Agent hardcoded the two exact test strings:
```diff
-    return "php -s" in command.script
+    return command.script.strip() == 'php -s localhost:8000' or command.script.strip() == 'php -t pub -s 0.0.0.0:8080'
```
The correct fix is `'-s' in command.script_parts` (flag `-s` anywhere in script parts).
Root cause: R7 source injection did **not trigger** because `assert match(command) → False` does not
produce a traceback frame inside `match()` (no exception raised inside the function body). Without
seeing the source function, the agent saw exactly two test parametrize cases and hardcoded them.

### R7 source injection — actual hit rate

R7 triggered in **1/9 bugs**: tornado-9, where `url_concat` raises `TypeError` internally
(frame appears in traceback). It did **not** trigger for:
- Assertion failures (`assert func(x) == expected`) — wrong return value, no intra-function frame
- Call-site TypeErrors (`got unexpected keyword argument`) — frame is in the test file
- Build/infrastructure failures (flake8, ImportError of C extension)

The bugs most affected by overfitting (thefuck-5/7, fastapi-1) all have assertion-failure or
call-site error patterns, so R7 did not help them structurally. thefuck-5 and fastapi-1 were fixed
by the R1–R3 changes (removal of overfit examples, cleaner prompt framing) rather than R7.

### Dataset exclusions (post-validation)

Two bugs are excluded from `bugsinpy-orchestrator-candidates-batch1.yaml` and future candidate
batches after post-mortem analysis:

**pandas-10 — excluded: build-system failure, out of scope**

Failure: `ImportError: C extension: No module named 'pandas._libs.interval' not built`.
The `pandas/_libs/interval.pyx` file is absent from the BugsInPy snapshot. The bug requires
build-system changes (setup.py extension registration), not function-level code. In 3 iterations
the agent searched for `interval.pyx`, failed to find it, and spent turns in confused build-system
exploration. Single-function APR is architecturally mismatched to build-system bugs.

**cookiecutter — excluded: entire project, all bug IDs**

All 4 cookiecutter bugs (1, 2, 3, 4) share the same root cause, confirmed by inspecting
`run_test.sh` for each bug ID in the BugsInPy repository:

```
cookiecutter-1: tox tests/test_generate_context.py::test_generate_context_decodes_non_ascii_chars
cookiecutter-2: tox tests/test_hooks.py::TestFindHooks::test_find_hook
cookiecutter-3: tox tests/test_read_user_choice.py::test_click_invocation
cookiecutter-4: tox tests/test_hooks.py::TestExternalHooks::test_run_failing_hook
```

Every bug calls `tox <test>`. The project's tox.ini requires py27/py33/py34/py35/pypy — none
installed in the Docker environment. tox returns exit_code 1 whenever any environment fails (even
if the only runnable environment, flake8, succeeds). The actual test functions never execute.
Result: **exit_code is always 1 regardless of whether the fix is correct, for every cookiecutter bug**.

All 4 cookiecutter bugs are commented out in `datasets/bugsinpy.yaml` with this explanation.

For cookiecutter-4 specifically, the agent's conceptual fix was correct (add `FailedHookException`,
raise it in `run_hook()` on non-zero exit), but:
1. The fix is unverifiable — no signal distinguishes "correct fix" from "still broken"
2. The agent introduced trailing whitespace that broke flake8, spending all 3 iterations on
   formatting rather than logic

This is a systemic issue with BugsInPy projects that used tox with legacy Python environments.
Pre-screen rule: exclude any bug whose `run_test.sh` begins with `tox` (not `pytest`).

### Remaining known issues (deferred)

| Issue | Description | Candidate fix |
|-------|-------------|---------------|
| thefuck-7 overfit persists | R7 does not trigger on assertion failures (wrong return value, no intra-function frame) | R7-EXT: lexical lookup of function name from test call site when traceback has no source frame |
| R7 overall hit rate low | Most APR failures are assertion-based, not exception-inside-function | R7-EXT covers this; depends on reliable call-site parsing |
| Legacy tox harnesses | BugsInPy bugs requiring py27/py3x return exit_code 1 regardless of fix | Pre-screening: exclude bugs where baseline exit=1 and only flake8 environment runs |

## References

| ID | Citation | Relevance |
|----|---------|-----------|
| REF-1 | Anthropic, "Building Effective Agents" (2024). https://www.anthropic.com/engineering/building-effective-agents | Tool-first design, anti-redundancy, stopping conditions, orchestrator patterns |
| REF-2 | Cursor team, prompt engineering guidelines (internal, 2024; summarized in community posts) | ABSOLUTE RULES pattern, "MUST read before edit", anti-wander stopping condition |
| REF-3 | Yang et al., "SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering", arXiv:2405.15232 (2024) | FileCommunicator / persistent file context; source-alongside-error design |
| REF-4 | Wang et al., "OpenHands: An Open Platform for AI Software Agents", arXiv:2407.16741 (2024) | CodeAct agent; context injection patterns; tool use discipline |
| REF-5 | Xia et al., "Automated Program Repair in the Era of Large Pre-trained Language Models", ICSE 2023 | APR survey; plausible-but-incorrect patch taxonomy; test overfitting as primary failure mode |
| REF-6 | Shi et al., "Large Language Models Are Few-Shot Testers", arXiv:2511.16858 (2024) | Test overfitting in APR: models satisfying test assertions without restoring correct semantics |
| REF-7 | Zhang et al., "AutoCodeRover: Autonomous Program Improvement", arXiv:2404.05427 (2024) | Explicit fault localization before repair; method-level context extraction |
| REF-8 | Xia et al., "Agentless: Demystifying LLM-based Software Engineering Agents", arXiv:2407.01489 (2024) | Two-phase localize→repair; injecting localization results into the repair prompt |
| REF-9 | Qwen team, "Qwen-Agent: Tool-Augmented LLM Agents" (2024); Microsoft AutoGen documentation | Small model behavior: concrete imperatives outperform abstract principles; few-shot benefit vs token cost |
| REF-10 | Liu et al., "Lost in the Middle: How Language Models Use Long Contexts", arXiv:2307.03172 (2023) | Position bias: models attend disproportionately to content at the beginning and end of context; rationale for source-before-test ordering |
