# Tasks — Spec 006: Observability Improvement

## Completadas

- [x] T01: Context variables + enriched models (ToolCallRecord 9 campos nuevos, APRHandoffNote, AgentHandoffRecord.handoff_note_json)
- [x] T02: Tool summary utilities (summarize_tool_result, summarize_tool_args con extracción por tool)
- [x] T03: JsonlEventObserver + build_observer integration
- [x] T04: Stable tool call IDs (UUID) + lifecycle_hooks enrichment (started_at, duration, summaries)
- [x] T05: MarkdownLiveObserver enriched ([agent] duration handoff notes)
- [x] T06: SQLite migration v4→v5 (9 columnas tool_calls + handoff_note_json)
- [x] T07: make_observable wrapper for FunctionTool + build_apr_tools
- [x] T08: Handoff notes con input_type/on_handoff (APRHandoffInput, context var)
- [x] T09: End-to-end integration + regression tests (209 tests pass)
- [x] T10: Facade input event (FacadeInputRecord, on_facade_input en observers, record_facade_input en telemetry, emisión en IterationRunner, tests)