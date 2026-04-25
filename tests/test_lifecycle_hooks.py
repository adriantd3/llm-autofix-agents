from __future__ import annotations

import asyncio
import unittest

from llm_autofix_agents.observability.lifecycle_hooks import APRRunHooks, infer_tool_status
from llm_autofix_agents.observability.models import ToolCallRecord


class _CaptureObserver:
    def __init__(self) -> None:
        self.tool_calls: list[ToolCallRecord] = []

    def on_tool_call(self, *, record: ToolCallRecord) -> None:
        self.tool_calls.append(record)


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

        asyncio.run(hooks.on_tool_start(context=None, agent=None, tool=_Tool()))
        asyncio.run(hooks.on_tool_end(context=None, agent=None, tool=_Tool(), result='{"ok": true}'))

        self.assertEqual(hooks.tool_call_count, 1)
        self.assertEqual(len(observer.tool_calls), 1)
        self.assertEqual(observer.tool_calls[0].tool_name, "read_file")
        self.assertEqual(observer.tool_calls[0].status, "success")


if __name__ == "__main__":
    unittest.main()
