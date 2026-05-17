# SPEC-014 Tasks

## Status: completed

## Tasks

- [x] Wire TestRunner sub-agent into orchestrator architecture
  - [x] Build test_runner agent in `orchestrator.py` with `as_tool(tool_name="run_tests")`
  - [x] Add SubAgent entry for test_runner in BuiltArchitecture
  - [x] Update tool_count (+2 for explore_code + run_tests)
  - [x] Set max_turns=5 for test_runner (initially 3, found too low)
- [x] Update orchestrator prompt for run_tests
  - [x] Replace `run_test_target` with `run_tests` in TOOLS section
  - [x] Update WORKFLOW step 6 to use `run_tests`
  - [x] Add `input` parameter guidance in tool description
- [x] Rewrite TestRunner instructions
  - [x] Add `/no_think` prefix for faster inference
  - [x] Markdown output format with verdict, failures, trace, action guidance
  - [x] Explicit `run_test_target` usage instruction
- [x] Update tool profiles
  - [x] Remove `run_test_target` from `APR_ORCHESTRATOR_MAIN_TOOLS`
  - [x] Remove stale comment about single-slot Ollama
- [x] Register `run_tests` tool metadata (ToolDescriptor + AgentProse classifier)
- [x] Make iteration.py references architecture-neutral (generic "test validation tool" instead of `run_test_target`)
- [x] Update tests for 2 sub-agents + 2 as_tool calls
- [x] Create batch configs
  - [x] `batches/bugsinpy-full/httpie-qwen3.5-9b.yaml` (iteration_timeout: 200s)
  - [x] `batches/bugsinpy-full/httpie-qwen3.5-27b.yaml` (iteration_timeout: 500s)
- [x] Run both batch comparisons
- [x] Analyze results vs. baseline
- [x] Investigate CUDA OOM root cause on httpie-1 and httpie-5
  - [x] Root cause: qwen3.5:9b (6.6GB) still loaded in VRAM when qwen3.5:27b (17GB) batch started
  - [x] httpie-5 OOM from KV cache accumulation after 3 successful runs
  - [x] Both classified as "retryable" HTTP 500 — wrong classification for capacity errors
- [x] Add Ollama model eviction before batch runs
  - [x] `BatchRunner._evict_stale_ollama_models()`: queries `GET /api/ps`, evicts non-target models via `POST /api/unload`
  - [x] Uses httpx (available via openai dependency)
  - [x] Only activates for ollama provider
- [x] Create SPEC-014 docs