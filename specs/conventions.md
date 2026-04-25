# Code Design and Development Conventions

This document defines the default code design and architecture conventions for this repository.

These conventions apply to all design, implementation, maintenance, and refactoring work. The goal is to keep the codebase maintainable, readable, testable, and easy to evolve without introducing unnecessary complexity.

## Engineering mindset

Code should be simple, explicit, modular, and aligned with the project domain.

Use SOLID, DRY, KISS, and design patterns as practical engineering tools, not as slogans. Prefer the simplest design that makes the current system understandable and extensible.

Before implementing a solution, think about:

- the responsibility of the code being changed,
- whether the change belongs in an existing module or a new cohesive module,
- whether the design will remain readable when another agent architecture, validation rule, provider, or workflow is added,
- whether duplication is accidental or a sign of a missing abstraction,
- whether a known design pattern can simplify the structure without overengineering it.

## Public API stability

Preserve public APIs unless the task explicitly allows changing them.

When changing a public API is necessary, update all call sites, tests, and relevant documentation. Explain the reason for the change.

## Separation of responsibilities

Each module, class, and function should have a clear responsibility.

Avoid mixing unrelated concerns such as configuration, execution flow, LLM/provider calls, validation, persistence, observability, git lifecycle, error construction, and output finalization in the same unit.

High-level orchestration code should describe the workflow. Low-level implementation details should live in dedicated modules, classes, or functions.

Public runners and workflows should remain thin orchestrators.

## Architecture boundaries

Architectural variants must be separated explicitly.

For APR architectures, avoid placing mono-agent, multi-agent, reviewer-based, planner-executor, or other architecture-specific logic in the same large runner.

Prefer a structure where each architecture has its own module or package, while shared contracts, state objects, validation, tools, observability, and result construction remain reusable.

A good architecture boundary should make it easy to answer:

- what is shared across architectures,
- what is specific to one architecture,
- where a new architecture should be added,
- which contract an architecture must implement,
- how the architecture is executed and validated.

## Design patterns

Use design patterns when they clarify responsibilities, reduce duplication, or make architectural variants easier to extend.

Do not introduce patterns mechanically. A pattern is justified only when it solves a current design problem.

Preferred patterns for this project include:

- Strategy: use it to separate alternative APR architectures, validation policies, tool profiles, model/provider selection, or patch-generation approaches behind a common contract.
- Template Method or workflow skeleton: use it when several architectures share the same high-level lifecycle but differ in specific steps.
- Pipeline or Chain of Responsibility: use it for ordered validation, post-processing, artifact generation, or decision checks.
- Facade: use it to hide noisy subsystems such as observability, git lifecycle, or tool execution behind a small high-level API.
- Adapter: use it to normalize external APIs, providers, SDK objects, or tool interfaces into project-specific contracts.
- Factory function: use it for centralized construction when creation depends on configuration. Avoid factories that only wrap a constructor.
- Result or Decision object: use it to represent validation outcomes, stop reasons, lifecycle results, or execution decisions explicitly.

Avoid unnecessary inheritance, generic managers, abstract base classes with one implementation, and pattern-heavy designs that make the code harder to follow.

## Strategy for APR architectures

Different agent architectures should be modeled as interchangeable strategies when they share the same external purpose: run an APR attempt and return a `RunOutput`.

The shared contract should express the architecture-level behavior, not its internal implementation.

Architecture-specific files should own only architecture-specific logic. Shared concerns should not be duplicated across architecture implementations.

Use Strategy when adding or separating:

- mono-agent baseline,
- planner-executor,
- reviewer/fixer loops,
- multi-agent debate,
- multi-agent specialist roles,
- alternative validation policies,
- alternative iteration policies.

The runner or entrypoint should select and execute an architecture strategy. It should not contain the internal flow of every architecture.

## Function and file size guidelines

Use these limits as default targets:

- Public orchestration functions should ideally stay below 80 lines.
- Internal functions should ideally stay below 60 logical lines.
- Files should ideally stay below 250 lines.
- Functions should ideally receive no more than 5-6 parameters.

These are guidelines, not absolute rules. If exceeding them is justified, explain why.

If a function needs many parameters, introduce a cohesive context, state, configuration, or result object.

## State and context objects

Avoid long functions with many loosely related mutable local variables.

Prefer explicit objects for cohesive concepts such as run configuration, run state, iteration context, validation result, artifact manifest, token usage, or finalization context.

State and context objects must clarify ownership. They should not be used as generic containers for unrelated data.

## Dataclass and domain model consistency

Dataclasses should form a coherent domain model.

Before introducing a new dataclass, check whether an existing type already represents the same concept. Avoid duplicating the same groups of fields across the repository.

When several structures need the same data, prefer extracting a shared value object and composing it into the larger structures.

Prefer composition first. Use inheritance or polymorphism only when there is a real domain relationship or meaningful shared behavior.

Do not use inheritance only to remove duplicated fields. Avoid broad base dataclasses that accumulate optional fields for many unrelated use cases.

The same concept should have one clear source of truth. Avoid parallel state where the same value is stored independently in multiple objects.

## Abstraction level

Keep one level of abstraction per function.

A function should not mix high-level workflow decisions with low-level implementation details.

If a function reads like a workflow, it should call well-named operations. If a function implements a low-level operation, it should not also control the full workflow.

## Duplication and refactoring trigger

When repeated code appears, stop and analyze whether it is acceptable duplication or a missing abstraction.

Do not continue copying similar blocks across the repository.

Repeated code is a refactoring trigger when it duplicates:

- lifecycle flow,
- validation branches,
- result or error construction,
- observability calls,
- git cleanup logic,
- provider/tool setup,
- token accounting,
- artifact persistence,
- architecture execution flow.

Before introducing more duplication, consider whether one of these is appropriate:

- extract a shared function,
- introduce a shared value object,
- introduce a strategy,
- introduce a validation pipeline,
- introduce a result builder or finalizer,
- introduce a facade for a noisy subsystem,
- move architecture-specific behavior behind a common contract.

Avoid abstractions that only hide duplicated lines without clarifying the domain.

## Result and error construction

Avoid duplicating result, error, and finalization logic across many branches.

If several branches create similar outputs, centralize that construction behind a focused builder, factory function, or finalizer.

The main flow should decide what happened. Dedicated result/finalization code should decide how to represent it.

## Observability

Observability is important, but it must not dominate business logic.

Prefer dedicated observability components or facades that expose high-level lifecycle methods.

Avoid constructing low-level observability records throughout unrelated execution logic.

## Lifecycle and cleanup

Lifecycle concerns should be explicit and centralized.

Avoid scattering setup, teardown, branch restoration, branch deletion, debug preservation, or cleanup behavior across many return branches.

Use dedicated lifecycle helpers or context managers when they make ownership clearer.

Cleanup behavior should be easy to reason about and test.

## Validation

Validation logic should be isolated from the main execution flow when it becomes non-trivial.

Validation should return explicit decisions or results instead of forcing the runner to embed every validation detail inline.

APR workflows should keep checks such as diff integrity, changed-files coherence, regression detection, no-progress detection, and completion criteria clearly separated from orchestration code.

When several validation checks are executed in sequence, prefer a small validation pipeline or chain of checks over a long inline block.

## Module organization

Group code by domain responsibility, not by incidental technical detail.

Prefer modules that represent project concepts such as architecture execution, iteration lifecycle, validation, artifacts, observability, git lifecycle, tools, providers, and results.

Avoid large generic modules that become dumping grounds for unrelated helpers.

If a module grows because it owns several responsibilities, split it by domain responsibility.

## Avoid cosmetic refactors

A change is not a meaningful refactor if it only moves code into private helper functions while preserving the same hard-to-read structure.

A useful structural change should reduce responsibilities, improve readability, reduce duplication, reduce parameter noise, and improve testability.

Do not claim a refactor is complete if the original god function or god module still owns most of the control flow.

## Avoid overengineering

Do not introduce abstractions just because they look clean.

Avoid interfaces with a single implementation, inheritance hierarchies without a real need, factories that only wrap constructors, generic managers with unclear ownership, and premature plugin systems.

Prefer the simplest structure that makes the current code understandable, maintainable, and suitable for the project timeline.

## Testing expectations

When changing code, run relevant tests and linting or formatting checks when available.

Add or update tests for extracted or newly introduced logic when reasonable.

For structural changes, prioritize tests around validation decisions, result construction, lifecycle behavior, error paths, architecture selection, and public API compatibility.

If validation cannot be run, explain why.

## Final response expectations

When completing implementation work, report:

- files changed,
- responsibilities added or moved,
- patterns or architectural boundaries introduced,
- behavior preserved,
- intentional behavior changes,
- tests or checks executed,
- remaining risks or follow-up work.
