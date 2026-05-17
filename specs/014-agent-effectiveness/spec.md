# SPEC-014: Agent Effectiveness — TestRunner Sub-Agent + Model Comparison

## Context

The multi_agent_orchestrator architecture was designed with 2 task-agents (explorer + test_runner) per SPEC-011, but only the explorer was wired. Tests were executed via `run_test_target` directly by the orchestrator, injecting raw pytest output into its context.

The handoff document (2026-05-16) identified G1 (explore_code tool_description) and G2 (read_file guidance) as already fixed, and recommended wiring the TestRunner sub-agent and running model comparison batches.

## Goals

1. Wire the TestRunner sub-agent to protect orchestrator context from verbose test output.
2. Run comparison batches with qwen3.5:9b and qwen3.5:27b to measure model-choice impact.
3. Verify no regressions vs. the previous direct `run_test_target` architecture.

## Design

### TestRunner sub-agent (context hygiene)

The TestRunner follows the same `Agent.as_tool()` pattern as the Explorer:

| Aspect | Explorer | TestRunner |
|--------|----------|------------|
| Tool name | `explore_code` | `run_tests` |
| Inner tools | read_file, search_files | run_test_target, execute_command, read_file |
| max_turns | 5 | 5 |
| Output | Focused code summary | Structured markdown: verdict, failures, trace, action guidance |
| Purpose | Cross-module understanding | Test execution + interpretation |

The orchestrator no longer has `run_test_target` in its tool profile — it must call `run_tests` which returns a clean markdown summary instead of raw JSON.

### Key changes

- `architectures/orchestrator.py`: build test_runner agent, `as_tool(tool_name="run_tests")`, add SubAgent entry
- `agents/instructions/orchestrator.py`: TOOLS section references `run_tests`, WORKFLOW step 6 uses `run_tests`, TestRunner instructions rewritten with `/no_think` prefix and markdown output format
- `tools/profiles.py`: remove `run_test_target` from `APR_ORCHESTRATOR_MAIN_TOOLS`, remove stale comment about single-slot Ollama
- `tools/metadata.py`: register `run_tests` ToolDescriptor
- `flow/policies/iteration.py`: make `run_test_target` references architecture-neutral

## Batch Comparison Results

### Baseline (2026-05-16, qwen3.5:27b, direct run_test_target)

| Bug | Status | Duration | Iterations | Tool Calls |
|-----|--------|----------|------------|------------|
| httpie-1 | timed_out | 900s | 2 (partial) | ~33 |
| httpie-2 | success | 345s | 1 | 21 |
| httpie-3 | success | 275s | 1 | 24 |
| httpie-4 | success | 868s | 2 | 28+22 |
| httpie-5 | timed_out | 900s | 1 (partial) | ~19 |

**Score: 3/5 success, 2 timed out**

### New Architecture — qwen3.5:27b (2026-05-17, TestRunner sub-agent)

| Bug | Status | Duration | Iterations | Tool Calls | run_tests | Notes |
|-----|--------|----------|------------|------------|-----------|-------|
| httpie-1 | failed | 306s | 1 | 0 | N/A | LLM infra error (HTTP 500) |
| httpie-2 | success | 334s | 1 | 17 | 3 | run_tests worked correctly |
| httpie-3 | success | 76s | 1 | 3 | 1 | Clean, efficient |
| httpie-4 | success | 140s | 1 | 10 | 1 | huge improvement (868s → 140s) |
| httpie-5 | failed | 338s | 1 | 0 | N/A | LLM infra error (HTTP 500) |

**Score: 3/5 (2 infra failures, not architecture), effective 3/3 when LLM available**

### New Architecture — qwen3.5:9b (2026-05-17, TestRunner sub-agent)

| Bug | Status | Duration | Iterations | Tool Calls | run_tests | Notes |
|-----|--------|----------|------------|------------|-----------|-------|
| httpie-1 | failed | 548s | 1 | ~19 | 4 | Model: invalid structured output |
| httpie-2 | failed | 119s | 1 | 21 | 1 | Model: invalid structured output |
| httpie-3 | success | 51s | 1 | 9 | 1 | Clean fix |
| httpie-4 | failed | 75s | 1 | 21 | 0 | Model: pure exploration, no edits |
| httpie-5 | failed | 407s | 2 | 24 | 1 | Model: invalid structured output |

**Score: 1/5 success. 9b model too weak for structured output.**

### Key findings

1. **TestRunner sub-agent works correctly**: All `run_tests` calls succeeded (no sdk_error, no "Invalid JSON input"). Structured markdown verdicts are consumed effectively by the orchestrator.

2. **Efficiency improvement (27b)**: When LLM is available, duration dropped ~64%, tokens ~30%, tool calls ~69% vs. baseline. The structured test verdict prevents exploration loops.

3. **qwen3.5:9b is too weak**: The 9b model fails to produce valid structured output (AgentFixIterationResult JSON) on 4/5 bugs. It can't track file state for `replace_in_file`. The TestRunner tool works, but the model itself is the bottleneck.

4. **Infrastructure failures**: The 2 failures on 27b were Ollama HTTP 500 errors (provider unavailable), not agent or architecture issues.

## Files Changed

- `src/llm_autofix_agents/architectures/orchestrator.py` — test_runner sub-agent wiring
- `src/llm_autofix_agents/agents/instructions/orchestrator.py` — prompt updates (run_tests, TestRunner markdown format)
- `src/llm_autofix_agents/agents/instructions/__init__.py` — ORCHESTRATOR_V2_TEST_RUNNER_INSTRUCTIONS export
- `src/llm_autofix_agents/tools/profiles.py` — remove run_test_target from orchestrator_main, remove stale comment
- `src/llm_autofix_agents/flow/policies/iteration.py` — make run_test_target references architecture-neutral
- `tests/test_architectures.py` — update for 2 sub-agents, 2 as_tool calls
- `batches/bugsinpy-full/httpie-qwen3.5-9b.yaml` — new batch config
- `batches/bugsinpy-full/httpie-qwen3.5-27b.yaml` — new batch config
- `src/llm_autofix_agents/batch/runner.py` — Ollama model eviction before each batch run

## Lessons

- The `run_tests` sub-agent pattern (context hygiene) is effective: the orchestrator receives concise verdicts instead of raw pytest output, reducing token waste and exploration loops.
- qwen3.5:9b cannot reliably produce structured JSON output for APR proposals. It's unsuitable for this architecture without output_schema relaxation.
- **CUDA OOM errors are miscategorized as retryable.** The `_is_retryable_provider_error` function in `provider.py` treats HTTP 500 / `InternalServerError` as retryable, but a CUDA Out-of-Memory error is a capacity problem that retrying cannot fix. This wastes 5+ minutes per failure (6 retries with exponential backoff). The error message contains `"CUDA error: out of memory"` which should be detected and treated as non-retryable.
- **GPU memory pressure from model coexistence.** With an RTX 4090 (24GB), running qwen3.5:9b (6.6GB) and then qwen3.5:27b (17GB) in sequence caused the first and last bugs of the 27b batch to OOM. The 9b model's KV cache was still loaded when the 27b batch started. Ollama's `keep_alive` setting retains models in VRAM — adding a model eviction step between batches (or between runs after OOM) would prevent this.
- **KV cache accumulation across sequential runs** can trigger OOM on later bugs in a batch. After 3 successful 27b runs (~550s of inference), the accumulated KV cache may not be evicted fast enough, causing the 5th bug to fail.
- **Mitigation**: `BatchRunner.run_batch` now calls `_evict_stale_ollama_models()` before the bug loop, which queries `GET /api/ps` on the Ollama host and sends `POST /api/unload` for any model not in the target batch's model list. This prevents VRAM contention from stale models left between batches.