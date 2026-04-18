from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from llm_autofix_agents.contracts import RunIdentity, RunInput, RunOutput, RunStatus, StopReason
from llm_autofix_agents.flow.observability import (
    build_observability_record,
    build_run_metrics,
    persist_observability_record,
)


class ObservabilityTests(unittest.TestCase):
    def test_persist_observability_uses_jsonl_when_mongodb_not_configured(self) -> None:
        with TemporaryDirectory() as tmp_dir, patch.dict("os.environ", {}, clear=True):
            repo_root = Path(tmp_dir)
            output = _build_run_output(run_id="run-obs-1")
            metrics = build_run_metrics(
                output=output,
                iterations=1,
                duration_seconds=1.25,
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
                metadata={},
            )
            record = build_observability_record(output=output, metrics=metrics, tool_calls=[])

            persistence = persist_observability_record(repo_root=repo_root, record=record)

            self.assertEqual(persistence["backend"], "jsonl")
            result_path = repo_root / persistence["path"]
            self.assertTrue(result_path.exists())
            lines = result_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertEqual(payload["run_id"], "run-obs-1")

    def test_persist_observability_fallbacks_to_jsonl_when_mongodb_fails(self) -> None:
        with TemporaryDirectory() as tmp_dir, patch.dict(
            "os.environ",
            {"MONGODB_CONNECTION_URL": "mongodb://example:27017"},
            clear=True,
        ), patch(
            "llm_autofix_agents.flow.observability._persist_to_mongodb",
            side_effect=RuntimeError("mongo unavailable"),
        ):
            repo_root = Path(tmp_dir)
            output = _build_run_output(run_id="run-obs-2")
            metrics = build_run_metrics(
                output=output,
                iterations=1,
                duration_seconds=2.0,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                metadata={"cost_per_1k_tokens_usd": 0.25},
            )
            record = build_observability_record(output=output, metrics=metrics, tool_calls=[])

            persistence = persist_observability_record(repo_root=repo_root, record=record)

            self.assertEqual(persistence["backend"], "jsonl")
            self.assertIn("fallback_reason", persistence)
            self.assertTrue((repo_root / persistence["path"]).exists())



def _build_run_output(*, run_id: str) -> RunOutput:
    run_input = RunInput(prompt="Fix failing tests")
    return RunOutput(
        identity=RunIdentity(
            run_id=run_id,
            run_fingerprint="0123456789abcdef",
            iteration=1,
            iteration_id=f"{run_id}-it01",
        ),
        status=RunStatus.SUCCESS,
        stop_reason=StopReason.COMPLETED,
        artifacts={"directory": "results/run-id/it01"},
        final_message=run_input.prompt,
    )


if __name__ == "__main__":
    unittest.main()
