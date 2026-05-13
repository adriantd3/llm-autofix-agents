"""SH1 validation: every APR function tool must have a registered ToolDescriptor.

This test fails immediately when a new tool is added without a descriptor,
preventing silent regression to 'unknown' summaries.
"""
from __future__ import annotations

import unittest

from llm_autofix_agents.tools.metadata import ToolResultKind, ToolStatus
from llm_autofix_agents.tools.profiles import APR_FUNCTION_TOOLS
from llm_autofix_agents.tools.registry import get, registered_names


class ToolDescriptorRegistryTest(unittest.TestCase):
    def test_all_apr_function_tools_have_descriptors(self) -> None:
        """Every tool in APR_FUNCTION_TOOLS must have a ToolDescriptor registered."""
        missing = []
        for tool in APR_FUNCTION_TOOLS:
            if get(tool.name) is None:
                missing.append(tool.name)
        self.assertEqual(
            missing,
            [],
            msg=f"Tools without ToolDescriptor (add register() to their module): {missing}",
        )

    def test_descriptor_result_kinds_are_valid(self) -> None:
        """All registered descriptors have a valid ToolResultKind."""
        valid_kinds = set(ToolResultKind)
        for name in registered_names():
            descriptor = get(name)
            assert descriptor is not None
            self.assertIn(
                descriptor.result_kind,
                valid_kinds,
                msg=f"Tool {name!r} has invalid result_kind: {descriptor.result_kind!r}",
            )

    def test_descriptor_summarize_args_returns_dict(self) -> None:
        """Each descriptor's summarize_args must return a dict for empty input."""
        for name in registered_names():
            descriptor = get(name)
            assert descriptor is not None
            result = descriptor.summarize_args({})
            self.assertIsInstance(
                result,
                dict,
                msg=f"Tool {name!r}: summarize_args({{}}) did not return dict",
            )

    def test_descriptor_summarize_result_returns_dict_for_ok_envelope(self) -> None:
        """Each JSON_ENVELOPE descriptor must parse a minimal ok=True result."""
        import json

        for name in registered_names():
            descriptor = get(name)
            assert descriptor is not None
            if descriptor.result_kind != ToolResultKind.JSON_ENVELOPE:
                continue
            raw = json.dumps({"ok": True})
            result = descriptor.summarize_result(raw)
            self.assertIsInstance(
                result,
                dict,
                msg=f"Tool {name!r}: summarize_result(ok=True JSON) did not return dict",
            )

    def test_descriptor_classify_status_ok_for_success(self) -> None:
        """JSON_ENVELOPE tools must return ToolStatus.OK for an ok=True payload."""
        import json

        for name in registered_names():
            descriptor = get(name)
            assert descriptor is not None
            if descriptor.result_kind != ToolResultKind.JSON_ENVELOPE:
                continue
            raw = json.dumps({"ok": True})
            status, _ = descriptor.classify_status(raw)
            self.assertEqual(
                status,
                ToolStatus.OK,
                msg=f"Tool {name!r}: classify_status(ok=True) returned {status!r}, expected OK",
            )

    def test_descriptor_classify_status_tool_error_for_failure(self) -> None:
        """JSON_ENVELOPE tools must return ToolStatus.TOOL_ERROR for ok=False."""
        import json

        for name in registered_names():
            descriptor = get(name)
            assert descriptor is not None
            if descriptor.result_kind != ToolResultKind.JSON_ENVELOPE:
                continue
            raw = json.dumps({"ok": False, "error": "test_error"})
            status, _ = descriptor.classify_status(raw)
            self.assertEqual(
                status,
                ToolStatus.TOOL_ERROR,
                msg=f"Tool {name!r}: classify_status(ok=False) returned {status!r}, expected TOOL_ERROR",
            )

    def test_descriptor_classify_status_sdk_error(self) -> None:
        """All tools must detect SDK error strings as ToolStatus.SDK_ERROR."""
        sdk_error = "An error occurred while running the tool. Please try again."
        for name in registered_names():
            descriptor = get(name)
            assert descriptor is not None
            status, _ = descriptor.classify_status(sdk_error)
            self.assertEqual(
                status,
                ToolStatus.SDK_ERROR,
                msg=f"Tool {name!r}: classify_status(sdk_error) returned {status!r}, expected SDK_ERROR",
            )


if __name__ == "__main__":
    unittest.main()
