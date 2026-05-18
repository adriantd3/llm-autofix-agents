# 015 — Context and Prompt Improvements from FastAPI Trace Analysis

**Date**: 2026-05-17  
**Branch**: chore/012/telemetry-observability-refactor  
**Batch analyzed**: `batch-bugsinpy-full-fastapi-orchestrator-20260517T101105Z`  
**Result before**: 6/16 resolved (37.5%)  

## Motivation

A full run of all 16 FastAPI bugs against `multi_agent_orchestrator` + `qwen3.5:9b` was analyzed trace-by-trace. 10 runs ended as `partial` (exit_code=1, stop_reason=max_iterations). Seven systemic issues were identified, plus one additional pattern discovered in post-analysis (change 8 below). None of the fixes are tied to a specific bug — each addresses a pattern visible in ≥2 runs.

---

## Issues and Changes

### 1 — Sub-agent `max_turns` too low (framework)

**Problem**: `explore_code` and `run_tests` are sub-agents invoked via `Agent.as_tool()`. Both had `max_turns=5`. When the underlying task required more internal tool calls (reading multiple files, parsing a long test output), the sub-agent returned a `MaxTurnsExceeded` SDK error instead of a result. This was observed in fastapi-13 iter 2, fastapi-14 iters 1–2, and fastapi-15 iters 2–3. It blocked the feedback loop: the main agent could not validate its edits.

**Fix**: `architectures/orchestrator.py` — `max_turns=5` → `max_turns=10` for both tools.

**Scope**: Systemic. Any bug that requires cross-module exploration or runs a test with complex output hits this limit.

---

### 2 — `write_file` in orchestrator tool profile (tool profile)

**Problem**: `APR_ORCHESTRATOR_MAIN_TOOLS` included `write_file`. In fastapi-6 iter 2, the agent used `write_file` to completely overwrite `fastapi/params.py` (7928 bytes), destroying the existing content and introducing import errors. This caused exit code 4 (collection error) for the remaining two iterations. The run ended in a worse state than it started.

**Fix**: `tools/profiles.py` — removed `write_file` from `APR_ORCHESTRATOR_MAIN_TOOLS`. The orchestrator should use `replace_in_file` for targeted edits to existing files. Creating new files from scratch is rarely needed in APR, and when it is, it represents a structural change that should be reconsidered.

**Scope**: Systemic. Any run where the agent decides to "rewrite" a file rather than patch it is at risk.

---

### 3 — Agent describes fix without calling tool (prompt)

**Problem**: In fastapi-3 iter 1, the agent's `reasoning_summary` described applying a correct fix to `fastapi/utils.py` but never called `replace_in_file`. Zero file changes. The iteration boundary warning fired, and the model's best exploration context was wasted. This is a known failure mode of smaller models: generating plan text that looks like tool output without actually invoking the tool.

**Fix**: Two places:
- `agents/instructions/_shared.py` — added `TOOL_EXECUTION_RULE` constant.
- `agents/instructions/orchestrator.py` — added as rule 7 in ABSOLUTE RULES.
- `flow/policies/iteration.py` — added to `_FAILURE_DRIVEN_INTRO`.

Text: *"Writing a fix in your reasoning or plan does NOT apply it to the repository. You MUST call replace_in_file (or replace_lines) to apply every change."*

**Scope**: Systemic for small models. Does not hurt large models.

---

### 4 — `write_file` misuse rule (prompt)

**Problem**: Companion to issue 2. Even with `write_file` in the tool profile, the agent should know it's destructive on existing files.

**Fix**: `agents/instructions/_shared.py` — added `REPLACE_NOT_WRITE_RULE` constant. Embedded in `ORCHESTRATOR_V2_MAIN_INSTRUCTIONS` as rule 8.

Text: *"Use replace_in_file for files that already exist. write_file overwrites the entire file — only use it to create files that do not exist yet."*

**Scope**: Defense-in-depth — even if `write_file` is re-added to a profile in the future.

---

### 5 — Workspace tree absent from continuation iterations (context gap)

**Problem**: `_build_workspace_tree` is already called in `_build_first_iteration_input` (iteration 1). But each iteration starts a **fresh agent run** — there is no shared conversation history between iterations. The workspace tree injected into iteration 1 is not available to iterations 2 and 3. Agents in iter 2+ had to rediscover the file layout from scratch, spending 3–8 turns on broad searches.

Observed in: fastapi-5 (agent searched for `**/*.py` returning 50 files), fastapi-10 (8 of 22 turns on route discovery), fastapi-13 (29 turns in iter 1 without locating the merge logic, iter 2 starts blind).

**Fix**: `flow/policies/iteration.py` — `build_iteration_input` now calls `_build_workspace_tree(repo_root)` in the continuation path (iterations 2+) and appends it before the task block.

**Scope**: Systemic. Affects every multi-iteration run on any repo.

---

### 6 — Continuation prompt doesn't signal when error is unchanged (context gap)

**Problem**: When an agent's edit had no effect on the failing code path, the continuation prompt for the next iteration only said "your previous attempt failed." It didn't distinguish between:
- *The test error changed* (edit affected the right path, but incorrectly)
- *The test error is identical* (edit touched the wrong path — or no edit was made)

This distinction is critical. In fastapi-10, the agent's iter 2 edit to `routing.py` was directionally correct (partial fix) but the continuation prompt didn't signal that the error was unchanged, so iter 3 pivoted away from the right location. In fastapi-11, all 3 iterations had the same error signature, but the agent kept tweaking the same wrong code path.

**Fix**: Two parts:
- `flow/policies/iteration.py` — `build_continuation_snapshot` gains `previous_test_signature: str | None = None`. When the current `test_execution.signature` matches `previous_test_signature` and the test still fails, the snapshot now includes: *"⚠ ERROR UNCHANGED: The test failure signature is identical to the previous iteration. Your edit had no effect on the failing code path."*
- `flow/policies/iteration.py` — added `extract_snapshot_test_signature(snapshot)` helper (parses the hash from the snapshot string).
- `flow/iteration/runner.py` — `_record_state` now extracts the previous signature from `state.latest_snapshot` before updating it, and passes it to `build_continuation_snapshot`.

**Scope**: Systemic. Benefits any multi-iteration run where a wrong edit is made.

---

### 7 — Pytest session header noise in test output (test output)

**Problem**: `compact_test_output` already filtered Python `Warning:` lines and collapsed repeats, but it preserved the pytest session header:
```
============================= test session starts ==============================
platform linux -- Python 3.8.x, pytest-6.x.x, ...
rootdir: /workspace, configfile: ...
collected 42 items
```
These lines consume prompt tokens without contributing diagnostic value. In fastapi-14, the large OpenAPI schema diff filled the output budget, leaving less room for the actual failure details.

**Fix**: `tools/text.py`:
- Added `_PYTEST_HEADER_LINE_RE` regex matching: separator lines (`===...===`), `platform `, `rootdir:`, `plugins:`, `cachedir:`, `collected N items`.
- Added `_filter_pytest_header(lines)` that strips matched lines but preserves separator lines that name a section (e.g., `===== FAILURES =====`, `===== short test summary info =====`) — the model needs section structure.
- Called in `compact_test_output` between the existing warning filter and the block-collapse step.

**Scope**: Systemic. Any pytest-based run benefits.

---

---

### 8 — No-edit + max_turns: continuation starts as lost as before (context gap)

**Problem**: When an iteration ends with `status="in_progress"` (agent cut off by max_turns) AND 0 file changes, the next iteration starts in an almost identical position to the first: same workspace tree, same traceback, but now with a useless `previous_message` saying "I explored X, Y, Z and found nothing." The `_ASSERTIVE_NO_EDIT_TASK` tells the agent to "make a change" but doesn't help it find WHERE.

This pattern was universal across the failed runs: fastapi-3 iters 1–2, fastapi-5 all 3 iters, fastapi-13 iters 1–2, fastapi-15 all 3 iters. In every case, the continuation agent repeated the same broad searches because it had no concrete starting point.

**Root cause split**:
- When max_turns hit: agent was actively exploring but got cut off before converging → needs a focused re-entry point
- When agent stopped itself (stuck): agent gave up → needs a different strategy hint
These two cases warrant different directives; the previous code treated them identically.

**Fix**: Three coordinated changes:

1. `flow/runtime/context.py` — Added `latest_test_execution: TestExecution | None = None` to `RunState` to make the raw test output available across iterations.

2. `flow/iteration/runner.py` — `_record_state` now sets `state.latest_test_execution = observation.test_execution`, and `_run_agent` passes both `latest_test_execution` and `previous_proposal_status` to `build_iteration_input`.

3. `flow/policies/iteration.py`:
   - `build_iteration_input` accepts `latest_test_execution` and `previous_proposal_status`.
   - When the previous iteration made 0 edits AND `repo_root` + `latest_test_execution` are available, calls `_extract_source_function_under_test` on the *latest* test output to re-localize. This re-injects the source function extracted from the traceback — the same machinery used in iteration 1, but now also available in iterations 2 and 3.
   - New `_build_task_block` helper produces one of four directives based on `(no_edit_previous, was_cut_off_by_max_turns, has_recovery_source)`:
     - **Normal case** (edits were made): "continue improving the repair strategy"
     - **Cut off + source found**: "the source function above is your starting point — read it, do not begin with broad searches"
     - **Cut off + no source**: "use the traceback to find the source file, read it, spend ≤3 discovery calls"
     - **Agent stopped itself + source found**: "read the function above, fix it, validate it"

**Scope**: Systemic. Benefits any multi-iteration run where an iteration is cut off by max_turns without progress, regardless of repo or bug type.

---

## Files Changed

| File | Change |
|------|--------|
| `src/llm_autofix_agents/architectures/orchestrator.py` | `max_turns` 5→10 for both sub-agent tools |
| `src/llm_autofix_agents/tools/profiles.py` | Removed `write_file` from `APR_ORCHESTRATOR_MAIN_TOOLS` |
| `src/llm_autofix_agents/agents/instructions/_shared.py` | Added `TOOL_EXECUTION_RULE`, `REPLACE_NOT_WRITE_RULE` |
| `src/llm_autofix_agents/agents/instructions/orchestrator.py` | Imported and embedded new rules as rules 7 and 8 |
| `src/llm_autofix_agents/flow/policies/iteration.py` | Workspace tree in continuation; unchanged-error signal; plan-without-tool rule in intro; `extract_snapshot_test_signature` helper |
| `src/llm_autofix_agents/flow/iteration/runner.py` | Pass `previous_test_signature` to `build_continuation_snapshot` |
| `src/llm_autofix_agents/tools/text.py` | Added `_filter_pytest_header`, called in `compact_test_output` |
| `tests/test_architectures.py` | Updated `max_turns` assertion 5→10 |
| `src/llm_autofix_agents/flow/runtime/context.py` | Added `latest_test_execution` field to `RunState` |

---

## What Was NOT Changed

- **Tool call budget (max_turns for main agent)**: The 10/20-turn limit per iteration was not raised. Failures weren't caused by needing more turns — exploration efficiency was the problem.
- **Max iterations**: Kept at 3. Adding a 4th iteration would not help runs stuck in wrong hypotheses.
- **Model**: Not changed. Successful runs (fastapi-12 in 8 calls, fastapi-16 in 15 calls) demonstrate the model is capable on single-file bugs. Context improvements should be validated first.
- **Per-bug prompt tuning**: No special-case logic for Decimal serialization, pydantic signatures, or WebSocket routing — those are one-off domain knowledge gaps.
- **Pre-localization (SBFL)**: Not added. The existing `_extract_source_function_under_test` already injects the innermost non-test traceback frame. SBFL would add significant harness complexity for uncertain gain on this dataset.

---

## Expected Impact

Changes 1, 5, 6 address the most tokens-wasted scenarios (sub-agent timeouts, re-discovery, wrong-path persistence). Changes 2, 3, 4 are defense-in-depth against destructive model behaviors. Change 7 is a marginal improvement but compounds with the others when output is long.

Estimated impact on this batch: 2–4 additional resolutions from the 10 partial failures, primarily from fastapi-10 (multi-file threading where the unchanged-error signal would redirect), fastapi-13/15 (where sub-agent timeouts blocked the feedback loop), and fastapi-5 (where workspace tree in iter 2 would prevent re-discovery from scratch).
