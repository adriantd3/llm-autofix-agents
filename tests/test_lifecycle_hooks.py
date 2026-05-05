from __future__ import annotations

import asyncio
import unittest

from llm_autofix_agents.observability.lifecycle_hooks import APRRunHooks, infer_tool_status
from llm_autofix_agents.observability.models import AgentHandoffRecord, ToolCallRecord


class _CaptureObserver:
    def __init__(self) -> None:
        self.tool_calls: list[ToolCallRecord] = []
        self.handoffs: list[AgentHandoffRecord] = []

    def on_tool_call(self, *, record: ToolCallRecord) -> None:
        self.tool_calls.append(record)

    def on_agent_handoff(self, *, record: AgentHandoffRecord) -> None:
        self.handoffs.append(record)


class _FakeAgent:
    def __init__(self, name: str) -> None:
        self.name = name


class LifecycleHooksTests(unittest.TestCase):
    def test_infer_tool_status_success(self) -> None:
        self.assertEqual(infer_tool_status('{"ok": true}'), ("success", True))

    def test_infer_tool_status_failed(self) -> None:
        self.assertEqual(infer_tool_status('{"ok": false}'), ("failed", False))

    def test_infer_tool_status_unknown(self) -> None:
        self.assertEqual(infer_tool_status("not-json"), ("unknown", None))

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
        self.assertEqual(observer.tool_calls[0].status, "success")

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


if __name__ == "__main__":
    unittest.main()
