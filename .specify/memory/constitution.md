<!--
Sync Impact Report
- Version change: 1.0.0 -> 1.1.0
- Modified principles:
	- I. Experimental Traceability First -> I. Traceable Failure-Signal Intake
	- II. Deterministic Orchestration with Controlled LLM Calls -> II. Deterministic Scaffold with Controlled Stochastic Agents
	- III. Test-Gated Repair Loop (NON-NEGOTIABLE) -> III. Evidence-Gated Repair Loop (NON-NEGOTIABLE)
	- Principle slot 4 -> IV. Reproducible and Isolated Execution
	- Principle slot 5 -> V. Cost, Time, and Evidence Accountability
- Added sections:
	- None
- Removed sections:
	- None
- Templates requiring updates:
	- .specify/templates/plan-template.md: updated
	- .specify/templates/spec-template.md: updated
	- .specify/templates/tasks-template.md: updated
	- .specify/templates/commands/*.md: pending (directory not present)
- Follow-up TODOs:
	- None
-->

# LLM Autofix Agents Constitution

## Core Principles

### I. Traceable Failure-Signal Intake
Every repair attempt MUST produce a complete execution trace: input signal
(failing tests, logs, issue tracker report, or structured bug report), selected
files, proposed patch, commands executed, validation evidence, and final
status. Any change without trace evidence is invalid for study inclusion.
Rationale: the TFM requires comparable and auditable results across
architectures and models while supporting future input modalities.

### II. Deterministic Scaffold with Controlled Stochastic Agents
The main workflow MUST remain system-first and deterministic at the scaffold
level (state machine, stages, budget limits, stop conditions). LLM behavior is
recognized as stochastic and MAY vary by run. LLMs MAY be invoked only at
predefined decision points (analysis, patch proposal, reflection), with
explicit input/output schemas and bounded tool permissions. Rationale: this
preserves evaluability without imposing unrealistic full determinism.

### III. Evidence-Gated Repair Loop (NON-NEGOTIABLE)
A patch is accepted only if the validation gate passes according to the
configured oracle. When executable tests exist, minimum acceptance is:
previously failing tests pass and no regression in relevant baseline tests.
When tests are missing or insufficient, acceptance MUST require explicit
alternative evidence (reproduction check from bug report, static checks,
human-review flag, or combined policy). The loop MUST enforce max-attempt
limits and clear termination reasons (fixed, exhausted, invalid state,
infrastructure error). Rationale: prevents unbounded iteration and separates
plausible from validated repairs across heterogeneous bug signals.

### IV. Reproducible and Isolated Execution
Each run MUST execute in an isolated environment (container or equivalent) with
pinned dependencies, explicit runtime metadata, and reproducible setup steps.
Repository state MUST be controlled per attempt (clean checkout, branch or
patch reset policy). Reproducibility is defined as controlled variance:
identical configuration MUST yield statistically comparable outcomes across
replications, not necessarily byte-identical trajectories. Rationale: strict
trajectory determinism is unrealistic with stochastic LLM components.

### V. Cost, Time, and Evidence Accountability
Each experiment MUST record latency, token or API usage (when available), and
compute/runtime cost proxies per attempt and per successful repair. Any claim
about architecture superiority MUST be backed by these metrics, not only fix
count. Rationale: research questions include efficiency, not just efficacy.

## Operational Constraints

- Primary implementation language MUST be Python 3.13 unless a documented
	exception is approved.
- Repository interaction MUST use explicit CLI commands (for example git,
	test runners, linters) and structured command logs.
- Tool access for agents MUST follow least privilege: read/search by default,
	write/apply only when a patch is selected, command execution whitelisted.
- Benchmark selections (for example QuixBugs, Defects4J subsets) MUST be
	documented with inclusion/exclusion criteria before result reporting.
- Security-sensitive operations (network, credentials, external write paths)
	MUST be denied by default and enabled only with explicit experiment policy.
- Failure-signal adapters MUST support at least one structured format for bug
	reports (for example issue title, reproduction steps, expected/actual result,
	and environment hints).

## Experimental Protocol and Quality Gates

1. Define experiment matrix before execution: architecture, model, budget,
	 timeout, max attempts, dataset split, and stopping policy.
2. Run baseline reproducibility check on a sample before full campaign.
3. For each bug instance, store artifact bundle with logs, patch diff,
	 environment metadata, and verdict.
4. Report outcomes with at least: repair rate, strict repair rate (if manual
	 or stronger oracle is available), median time, and cost distribution.
5. Document threats to validity for dataset bias, flaky tests,
	 non-deterministic tools, and model drift.

## Governance

This constitution supersedes local workflow habits for this repository.
Amendments require: (a) a written proposal, (b) impact analysis on templates
and active specs, and (c) version update by semantic rules.

Versioning policy:
- MAJOR: incompatible governance change, principle removal, or redefinition.
- MINOR: new principle/section or materially expanded mandatory guidance.
- PATCH: wording clarifications, typo fixes, and non-semantic edits.

Compliance review expectations:
- Every plan MUST include a Constitution Check with pass/fail evidence.
- Every spec MUST define measurable success criteria aligned with this
	constitution.
- Every tasks file MUST include work for reproducibility, validation, and
	experiment logging when applicable.

**Version**: 1.1.0 | **Ratified**: 2026-04-08 | **Last Amended**: 2026-04-08
