from __future__ import annotations

import asyncio
import json
import unittest

from llm_autofix_agents.observability.events import AgentHandoff, ObservabilityEvent, ToolCalled
from llm_autofix_agents.observability.lifecycle_hooks import APRRunHooks
from llm_autofix_agents.observability.models import AgentHandoffRecord, ToolCallRecord


class _CaptureObserver:
    def __init__(self) -> None:
        self.tool_calls: list[ToolCallRecord] = []
        self.handoffs: list[AgentHandoffRecord] = []

    def emit(self, event: ObservabilityEvent) -> None:
        if isinstance(event, ToolCalled):
            self.tool_calls.append(event.record)
        elif isinstance(event, AgentHandoff):
            self.handoffs.append(event.record)


class _FakeAgent:
    def __init__(self, name: str) -> None:
        self.name = name


class LifecycleHooksTests(unittest.TestCase):
    def test_on_tool_end_records_tool_call(self) -> None:
        observer = _CaptureObserver()
        hooks = APRRunHooks(
            observer=observer,
            run_id="run-1",
            iteration_id="run-1-it01",
            agent_execution_id="run-1-it01-agent01",
        )

        class _Tool:
            name = "read_file"

        asyncio.run(hooks.on_tool_start(context=None, agent=_FakeAgent("baseline"), tool=_Tool()))
        asyncio.run(hooks.on_tool_end(context=None, agent=_FakeAgent("baseline"), tool=_Tool(), result='{"ok": true}'))

        self.assertEqual(hooks.tool_call_count, 1)
        self.assertEqual(len(observer.tool_calls), 1)
        self.assertEqual(observer.tool_calls[0].tool_name, "read_file")
        self.assertEqual(observer.tool_calls[0].status, "ok")

    def test_on_tool_end_includes_agent_name(self) -> None:
        observer = _CaptureObserver()
        hooks = APRRunHooks(
            observer=observer,
            run_id="run-1",
            iteration_id="run-1-it01",
            agent_execution_id="run-1-it01-agent01",
        )

        class _Tool:
            name = "search_files"

        asyncio.run(hooks.on_tool_start(context=None, agent=_FakeAgent("localizer"), tool=_Tool()))
        asyncio.run(hooks.on_tool_end(context=None, agent=_FakeAgent("localizer"), tool=_Tool(), result='{"ok": true}'))

        self.assertEqual(len(observer.tool_calls), 1)
        self.assertEqual(observer.tool_calls[0].agent_name, "localizer")

    def test_on_tool_end_captures_args_summary_from_tool_arguments(self) -> None:
        observer = _CaptureObserver()
        hooks = APRRunHooks(
            observer=observer,
            run_id="run-1",
            iteration_id="run-1-it01",
            agent_execution_id="run-1-it01-agent01",
        )

        class _Tool:
            name = "read_file"

        class _FakeContext:
            tool_arguments = '{"path": "src/main.py", "start_line": 1, "end_line": 10}'

        asyncio.run(hooks.on_tool_start(context=_FakeContext(), agent=_FakeAgent("localizer"), tool=_Tool()))
        asyncio.run(
            hooks.on_tool_end(
                context=_FakeContext(), agent=_FakeAgent("localizer"), tool=_Tool(), result='{"ok": true}'
            )
        )

        self.assertEqual(len(observer.tool_calls), 1)
        record = observer.tool_calls[0]
        self.assertIsNotNone(record.args_summary_json)
        self.assertIn("src/main.py", record.args_summary_json)

    def test_on_agent_start_sets_current_agent(self) -> None:
        observer = _CaptureObserver()
        hooks = APRRunHooks(
            observer=observer,
            run_id="run-1",
            iteration_id="run-1-it01",
            agent_execution_id="run-1-it01-agent01",
        )
        asyncio.run(hooks.on_agent_start(context=None, agent=_FakeAgent("triage")))
        self.assertEqual(hooks._current_agent_name, "triage")

    def test_on_handoff_emits_handoff_record(self) -> None:
        observer = _CaptureObserver()
        run_agent_ids = {"triage": "ra-triage", "localizer": "ra-localizer"}
        hooks = APRRunHooks(
            observer=observer,
            run_id="run-1",
            iteration_id="run-1-it01",
            agent_execution_id="run-1-it01-agent01",
            run_agent_ids=run_agent_ids,
            iteration_index=1,
        )
        asyncio.run(
            hooks.on_handoff(
                context=None,
                from_agent=_FakeAgent("triage"),
                to_agent=_FakeAgent("localizer"),
            )
        )

        self.assertEqual(len(observer.handoffs), 1)
        record = observer.handoffs[0]
        self.assertEqual(record.from_agent_name, "triage")
        self.assertEqual(record.to_agent_name, "localizer")
        self.assertEqual(record.from_run_agent_id, "ra-triage")
        self.assertEqual(record.to_run_agent_id, "ra-localizer")

    def test_multiple_handoffs_increment_index(self) -> None:
        observer = _CaptureObserver()
        hooks = APRRunHooks(
            observer=observer,
            run_id="run-1",
            iteration_id="run-1-it01",
            agent_execution_id="run-1-it01-agent01",
            run_agent_ids={},
            iteration_index=1,
        )
        asyncio.run(hooks.on_handoff(context=None, from_agent=_FakeAgent("triage"), to_agent=_FakeAgent("localizer")))
        asyncio.run(hooks.on_handoff(context=None, from_agent=_FakeAgent("localizer"), to_agent=_FakeAgent("patcher")))

        self.assertEqual(len(observer.handoffs), 2)
        self.assertIn("handoff001", observer.handoffs[0].handoff_id)
        self.assertIn("handoff002", observer.handoffs[1].handoff_id)


class ContextSnapshotTests(unittest.TestCase):
    def _make_hooks(self) -> APRRunHooks:
        return APRRunHooks(
            observer=_CaptureObserver(),
            run_id="run-1",
            iteration_id="run-1-it01",
            agent_execution_id="run-1-it01-agent01",
        )

    def _run_tool(self, hooks: APRRunHooks, tool_name: str, args_json: str, result: str) -> None:
        class _Tool:
            pass
        _Tool.name = tool_name

        class _Ctx:
            pass
        _Ctx.tool_arguments = args_json

        asyncio.run(hooks.on_tool_start(context=_Ctx(), agent=_FakeAgent("agent"), tool=_Tool()))
        asyncio.run(hooks.on_tool_end(context=_Ctx(), agent=_FakeAgent("agent"), tool=_Tool(), result=result))

    def test_snapshot_returns_none_when_no_tools_called(self) -> None:
        hooks = self._make_hooks()
        self.assertIsNone(hooks.extract_context_snapshot())

    def test_snapshot_captures_search_hits(self) -> None:
        hooks = self._make_hooks()
        result = '{"ok": true, "results": [{"path": "src/foo.py", "line": 42, "match": "def bar"}]}'
        self._run_tool(hooks, "search_files", '{"query": "bar"}', result)
        snapshot = hooks.extract_context_snapshot()
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertIn("src/foo.py:42", snapshot)
        self.assertIn("def bar", snapshot)

    def test_snapshot_excludes_test_paths(self) -> None:
        hooks = self._make_hooks()
        result = '{"ok": true, "results": [{"path": "test/test_foo.py", "line": 10, "match": "def bar"}, {"path": "src/foo.py", "line": 42, "match": "def bar"}]}'
        self._run_tool(hooks, "search_files", '{"query": "bar"}', result)
        snapshot = hooks.extract_context_snapshot()
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertNotIn("test/test_foo.py", snapshot)
        self.assertIn("src/foo.py", snapshot)

    def test_snapshot_captures_read_files(self) -> None:
        hooks = self._make_hooks()
        self._run_tool(hooks, "read_file", '{"path": "src/foo.py", "start_line": 100, "end_line": 150}', '{"ok": true}')
        snapshot = hooks.extract_context_snapshot()
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertIn("src/foo.py:100-150", snapshot)

    def test_snapshot_captures_read_file_without_line_range(self) -> None:
        hooks = self._make_hooks()
        self._run_tool(hooks, "read_file", '{"path": "src/utils.py"}', '{"ok": true}')
        snapshot = hooks.extract_context_snapshot()
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertIn("src/utils.py", snapshot)

    def test_snapshot_captures_edit_attempt_ok(self) -> None:
        hooks = self._make_hooks()
        self._run_tool(hooks, "replace_in_file", '{"path": "src/foo.py"}', '{"ok": true}')
        snapshot = hooks.extract_context_snapshot()
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertIn("replace_in_file(src/foo.py) → ok", snapshot)

    def test_snapshot_captures_edit_attempt_failed(self) -> None:
        hooks = self._make_hooks()
        self._run_tool(hooks, "replace_in_file", '{"path": "src/foo.py"}', '{"ok": false, "error": "old_text_not_found"}')
        snapshot = hooks.extract_context_snapshot()
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertIn("failed:old_text_not_found", snapshot)

    def test_reset_clears_all_accumulated_context(self) -> None:
        hooks = self._make_hooks()
        result = '{"ok": true, "results": [{"path": "src/foo.py", "line": 1, "match": "x"}]}'
        self._run_tool(hooks, "search_files", '{"query": "x"}', result)
        self._run_tool(hooks, "read_file", '{"path": "src/foo.py"}', '{"ok": true}')
        self.assertIsNotNone(hooks.extract_context_snapshot())
        hooks.reset_context_snapshot()
        self.assertIsNone(hooks.extract_context_snapshot())

    def test_snapshot_deduplicates_read_file_entries(self) -> None:
        hooks = self._make_hooks()
        self._run_tool(hooks, "read_file", '{"path": "src/foo.py", "start_line": 1, "end_line": 50}', '{"ok": true}')
        self._run_tool(hooks, "read_file", '{"path": "src/foo.py", "start_line": 1, "end_line": 50}', '{"ok": true}')
        snapshot = hooks.extract_context_snapshot()
        assert snapshot is not None
        self.assertEqual(snapshot.count("src/foo.py:1-50"), 1)

    def test_snapshot_caps_search_hits_at_five(self) -> None:
        hooks = self._make_hooks()
        hits = [{"path": f"src/file{i}.py", "line": i, "match": f"match{i}"} for i in range(10)]
        result = f'{{"ok": true, "results": {json.dumps(hits)}}}'
        self._run_tool(hooks, "search_files", '{"query": "x"}', result)
        snapshot = hooks.extract_context_snapshot()
        assert snapshot is not None
        # At most 5 hits should appear
        hit_count = sum(1 for i in range(10) if f"src/file{i}.py" in snapshot)
        self.assertLessEqual(hit_count, 5)


if __name__ == "__main__":
    unittest.main()
