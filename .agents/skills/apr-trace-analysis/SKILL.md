---
name: apr-trace-analysis
description: Analyze APR (automated program repair) agent run traces from live.md files to understand what happened step-by-step, identify failure patterns, and find improvements to prompts or context the agent receives — grounded in state-of-the-art context engineering practices. Use this skill whenever the user opens or references a live.md file, asks why an agent failed or what it did, wants to understand a batch run result, mentions "trace", "iteration", "tool calls", "what happened in this run", "why did the agent fail", or wants to improve their APR prompts/config based on observations. Also trigger when the user shows multiple run results and asks for patterns.
---

# APR Trace Analysis

Your job is to read agent execution traces and produce a clear diagnosis. The two key outputs are:

1. **What happened** — a factual account of what the agent did, step by step
2. **What to improve** — actionable changes to the context or prompt the agent receives, grounded in what top-tier systems do differently

The discipline here is **not overfitting**: you're looking for changes that would help across the next 100 bugs, not just the one you're reading.

## Sources of information

Each run directory contains two complementary files. Use both.

### events.jsonl — the primary source

A newline-delimited JSON file where each line is one event. This is the authoritative, structured record of everything that happened. Key event types:

| Event | Key fields |
|-------|-----------|
| `run_started` | `architecture`, `problem_id`, `benchmark_name` |
| `agent_registered` | `agent_name`, `agent_role`, `model_config`, `tool_profile` — shows what tools the agent had |
| `facade_input` | `input_text` — the **exact full prompt** the agent received |
| `test_execution` | `phase` (baseline/validation), `exit_code`, `timed_out`, `duration_seconds` |
| `iteration_started/finished` | `iteration_index`, `status`, `stop_reason`, `input_tokens`, `output_tokens`, `test_exit_code` |
| `agent_execution_started/finished` | `reasoning_summary`, `confidence`, `input_tokens`, `output_tokens`, `tool_calls_count` |
| `tool_call` | `tool_name`, `status`, `success`, `args_summary_json`, `result_summary_json`, `duration_seconds` |
| `file_change` | `path`, `change_type`, `additions`, `deletions` |
| `run_finished` | `final_status`, `resolved`, `stop_reason`, `total_tokens`, `duration_seconds` |

The `args_summary_json` and `result_summary_json` fields on `tool_call` events are structured JSON — parse them to see exactly what the agent searched for and what came back. The `facade_input.input_text` is the complete prompt the agent actually received, including all template variables resolved.

### live.md — the human-readable companion

A formatted Markdown render of the same run. Useful for reading reasoning summaries and iteration structure at a glance:

```
## Agent                    ← model, architecture, tool profile
- test phase=baseline       ← baseline test run BEFORE the agent touched anything

## Iteration N              ← one outer-loop attempt (the orchestrator can retry)
  ### Facade input          ← the prompt given to the agent (also in events.jsonl)
  ### Agent execution       ← all tool calls the agent made
    tool 001: [name] → ok/tool_error
    ...
  ### Agent execution finished
    - status: in_progress | failed | success
    - reasoning_summary: ...
  ### Iteration N result
    - status: ...
    - stop_reason: None | ...
    - changed_files_count: N

## Run finished
  - status: failed | success | partial
  - stop_reason: tool_failure | no_progress | completed | max_iterations | ...
  - total_iterations: N
```

When the two sources conflict, trust events.jsonl. A batch directory contains multiple run directories, one per bug.

## Step-by-step reading protocol

Work through the run in this order:

**1. What did the agent receive?** — Read the `facade_input` event and extract `input_text`. What was the error output passed in? Was there a workspace map or directory tree? What variables were resolved? This is what the agent started with — everything it had to discover on top of this was a context gap.

**2. What tools did the agent have?** — Check `agent_registered` events for `tool_profile`. This tells you the agent's affordances: can it run commands? Does it have a file tree tool? Does it have a focused test runner?

**3. Baseline test** — Find `test_execution` events with `phase=baseline`. What was the `exit_code`? Exit 1 = test fails as expected (correct setup). Exit 2/4 = infrastructure problem before the agent even started.

**4. Iteration structure** — Read `iteration_finished` events: how many iterations, what `status` and `stop_reason`, and what `test_exit_code` did each produce. An iteration with `changed_files_count: 0` and `status: in_progress` means the model produced no usable output.

**5. Tool call sequence** — Parse the `tool_call` events in order. For each one read `args_summary_json` and `result_summary_json` as JSON. Track two things:
   - What was the agent trying to find, and how many turns did it take to find it?
   - What did each search or read return — signal or noise?

   Normal exploration before a first edit: 3-6 tool calls. Above 10 is a sign the agent is lost or the context didn't give it enough to start from.

**6. File changes** — Check `file_change` events: which files changed (`path`, `change_type`), and whether changes were in source or test files.

**7. Final outcome** — Read `run_finished`: `resolved` (bool), `final_status`, `stop_reason`, `total_tokens`, `duration_seconds`. Cross-check `total_iterations` against the actual `iteration_finished` count (a known framework bug hardcodes `total_iterations: 1` when an exception is caught in the outer loop).

**Exit code reference**
- exit 0 = passed
- exit 1 = test failures (normal — the agent didn't fix it)
- exit 2 = workspace not compiled — infrastructure issue
- exit 4 = pytest collection error
- exit 124 = timeout
- `stop_reason: tool_failure` = unhandled exception in the framework (often a ProviderCallError when the model hits max turns)

## Context engineering audit

This is the core of the analysis. After reading the trace, ask these questions about the **context the agent received**:

**What did the agent have to discover that it could have been told?**

Read `facade_input.input_text` and list what information it contains. Then read the first N tool calls and list what the agent had to figure out. The delta between these two lists is the context gap.

Top-tier systems (Claude Code, SWE-agent, OpenHands, ACR) consistently provide:

- **Workspace tree at startup** — the agent knows the full directory structure before calling any tool. Without this, agents waste 3-5 turns on `list_files` before reaching the target file.
- **Pre-localized fault location** — systems like ACR run static analysis or SBFL before the agent runs, providing something like "the bug is likely in `sessions.py:104`". This eliminates the localization phase entirely.
- **Structured test output** — raw pytest output includes deprecation warnings, import errors, and noise that distract models. Top systems parse this to surface only the relevant assertion failure and innermost traceback frame.
- **Explicit tool affordances** — the system prompt explains what each tool does and its limitations (e.g., "list_files shows paths relative to the workspace root, not the container root"). Agents that don't know their tool set boundaries waste turns on failed attempts.

For each tool call sequence you observe, ask: "Did the agent discover this because it had to, or because the harness didn't provide it?"

**Was the test output signal or noise?**

Check what `facade_input.input_text` contains in the error output section. Then trace what the agent did with it:
- If the agent pursued a DeprecationWarning instead of the actual traceback → the output had too much noise
- If the agent spent turns searching for the file named in the traceback → the traceback was present but the agent couldn't map module paths to workspace paths (missing workspace tree)
- If the agent read many files to reconstruct what the bug was → pre-localization could have eliminated this

**What does the system prompt tell the agent it cannot do, and did the agent respect those rules?**

Find the rules in `facade_input.input_text`. Then check `file_change` events and tool call patterns against them:
- Rule violations (editing test files, redundant identical tool calls) can indicate: the rule is buried and not salient, the rule has no consequence stated, or the model capacity is insufficient to track constraints across many turns
- A rule that was followed is not necessarily well-written — if the agent followed it by accident or by default model behavior, it won't hold under harder bugs

## Failure taxonomy

Classify each issue into exactly one root cause:

| Category | Meaning | Typical signal |
|----------|---------|----------------|
| **Infrastructure** | Workspace wasn't ready before the agent started | Baseline exit code ≠ 1, `ModuleNotFoundError` before agent touches anything |
| **Dataset** | Benchmark data is incomplete or wrong | requirements.txt missing the package, wrong test path in bug metadata |
| **Context gap** | The agent lacked information it needed to operate efficiently | Excessive exploration, wrong path attempts, distracted by noise in test output |
| **Prompt/instruction** | Instructions are misleading or a needed rule is missing | Agent violates an existing rule, or behavior the instructions could have prevented |
| **Model capability** | The model lacks the reasoning or knowledge for this difficulty | Empty output, fails at multi-step inference across files, wrong path prefixes consistently |
| **Framework bug** | A bug in the APR runner itself | `total_iterations: 1` when 2 ran, test command doesn't activate venv |

One trace can have issues from multiple categories.

## The systemic vs. one-off test

Before writing a recommendation, ask: **"Would this issue affect a different bug on the same repo, or a different repo entirely?"**

- If yes → systemic. Worth a fix.
- If only this specific bug (e.g., "the model didn't know about `RequestsCookieJar`") → one-off. Note it, don't recommend a fix.

Examples:
- "Agent spent 6 turns on list_files because it didn't know the workspace tree" → systemic (every bug on every repo)
- "Agent was distracted by DeprecationWarnings in 3 of 4 runs" → systemic (fix the test output filter)
- "Agent tried `httpie/httpie/sessions.py` because the workspace has a nested dir structure not described in the prompt" → systemic (workspace map would prevent this)
- "Agent couldn't reconstruct `get_filename_max_length` from test assertions" → one-off (hard bug, not a prompt issue)

## Output format

---

### What happened
One paragraph: what ran, what the agent received, overall result, main failure mode.

### Iteration walkthrough
For each iteration: how many tool calls, key decision points, what the agent found vs. what it was looking for, how it ended.

### Context gaps
What did the agent have to discover that it could have been told upfront? For each gap:

**[Gap name]**
- *Evidence*: the tool calls that show the agent searching for this
- *What top systems do*: what Claude Code / SWE-agent / ACR provides that addresses this
- *Recommendation*: specific change to the facade input, system prompt, or harness

### Other issues
Any infrastructure, framework, or model issues that are separate from the context/prompt.

### What NOT to change
Things that look like failures but are just hard bugs or model limitations — where changing the prompt wouldn't help.

---

## Calibration

- If the agent found the right file but wrote the wrong fix → model capability issue, not context. Don't add more instructions.
- If the agent found the wrong file entirely → likely a context gap. What would have pointed it to the right one?
- Don't recommend adding more rules to the prompt unless you can show the agent violated an existing rule first. More rules = more noise.
- Don't recommend switching models based on a single observation. Note it if 3+ runs show the same model-specific failure.
- Don't recommend per-bug fixes. Your output should be useful for the next 100 bugs.
- If you're not sure whether something is a context gap or model capability, say so explicitly rather than picking one.
