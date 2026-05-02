from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import yaml

from llm_autofix_agents.batch.config import (
    BugEntry,
    DatasetConfig,
    GlobalSettings,
    LLMSettings,
    expand_bugs,
    load_batch_config,
    load_dataset_config,
)
from llm_autofix_agents.batch.prompt import capture_error_output, generate_prompt
from llm_autofix_agents.batch.runner import _parse_json_output, _truncate
from llm_autofix_agents.batch.summary import BatchSummary, BugRunResult, new_batch_id
from llm_autofix_agents.contracts import RunArchitecture


class TestBugEntry(unittest.TestCase):
    def test_valid_bug_entry(self):
        bug = BugEntry(id="gcd", program="python_programs/gcd.py", test="python_testcases/test_gcd.py")
        self.assertEqual(bug.id, "gcd")
        self.assertEqual(bug.program, "python_programs/gcd.py")

    def test_bug_entry_strips_whitespace(self):
        bug = BugEntry(id=" gcd ", program=" python_programs/gcd.py ", test=" test_gcd.py ")
        self.assertEqual(bug.id, "gcd")
        self.assertEqual(bug.program, "python_programs/gcd.py")

    def test_bug_entry_with_override_test_command(self):
        bug = BugEntry(
            id="gcd",
            program="python_programs/gcd.py",
            test="python_testcases/test_gcd.py",
            test_command="custom test command",
        )
        self.assertEqual(bug.test_command, "custom test command")

    def test_bug_entry_rejects_empty_id(self):
        with self.assertRaises(ValueError):
            BugEntry(id="", program="p.py", test="t.py")

    def test_bug_entry_rejects_extra_fields(self):
        with self.assertRaises(ValueError):
            BugEntry(id="gcd", program="p.py", test="t.py", unknown_field="x")


class TestDatasetConfig(unittest.TestCase):
    def test_resolve_test_command_from_template(self):
        dataset = DatasetConfig(
            name="test",
            repository="https://example.com",
            branch="main",
            language="python",
            test_command_template="pytest test_{bug_id}.py",
            bugs=[BugEntry(id="gcd", program="p.py", test="t.py")],
        )
        bug = dataset.bugs[0]
        self.assertEqual(dataset.resolve_test_command(bug), "pytest test_gcd.py")

    def test_resolve_test_command_override(self):
        dataset = DatasetConfig(
            name="test",
            repository="https://example.com",
            branch="main",
            language="python",
            test_command_template="pytest test_{bug_id}.py",
            bugs=[BugEntry(id="gcd", program="p.py", test="t.py", test_command="custom command")],
        )
        bug = dataset.bugs[0]
        self.assertEqual(dataset.resolve_test_command(bug), "custom command")

    def test_load_dataset_config_from_yaml(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data = {
                "name": "test-dataset",
                "repository": "https://example.com/repo.git",
                "branch": "main",
                "language": "python",
                "test_command_template": "pytest test_{bug_id}.py",
                "bugs": [
                    {"id": "gcd", "program": "p.py", "test": "t.py"},
                    {"id": "flatten", "program": "p2.py", "test": "t2.py"},
                ],
            }
            path = Path(tmp_dir) / "dataset.yaml"
            path.write_text(yaml.dump(data), encoding="utf-8")
            config = load_dataset_config(path)
            self.assertEqual(config.name, "test-dataset")
            self.assertEqual(len(config.bugs), 2)
            self.assertEqual(config.bugs[0].id, "gcd")


class TestLLMSettings(unittest.TestCase):
    def test_resolve_agent_models_mono(self):
        settings = LLMSettings(model="qwen3.5:9b")
        result = settings.resolve_agent_models(RunArchitecture.MONO_AGENT)
        self.assertEqual(result, {"main": "qwen3.5:9b"})

    def test_resolve_agent_models_handoff(self):
        settings = LLMSettings(model="qwen3.5:9b")
        result = settings.resolve_agent_models(RunArchitecture.MULTI_AGENT_HANDOFF)
        self.assertEqual(
            result,
            {
                "triage": "qwen3.5:9b",
                "localizer": "qwen3.5:9b",
                "patcher": "qwen3.5:9b",
                "validator": "qwen3.5:9b",
            },
        )

    def test_resolve_agent_models_custom(self):
        settings = LLMSettings(model="qwen3.5:9b", agent_models={"main": "custom-model"})
        result = settings.resolve_agent_models(RunArchitecture.MONO_AGENT)
        self.assertEqual(result, {"main": "custom-model"})


class TestGlobalSettings(unittest.TestCase):
    def test_valid_global_settings(self):
        settings = GlobalSettings(
            architecture=RunArchitecture.MONO_AGENT,
            llm=LLMSettings(model="qwen3.5:9b"),
            prompt_template="Fix {bug_id}",
        )
        self.assertEqual(settings.architecture, RunArchitecture.MONO_AGENT)
        self.assertEqual(settings.max_iterations, 6)
        self.assertTrue(settings.capture_errors)

    def test_default_values(self):
        settings = GlobalSettings(
            architecture="mono_agent",
            llm={"model": "test"},
            prompt_template="Fix {bug_id}",
        )
        self.assertEqual(settings.max_iterations, 6)
        self.assertEqual(settings.timeout_seconds, 300)


class TestBatchConfig(unittest.TestCase):
    def _create_test_files(self, tmp_dir: Path, bugs: list[str] | None = None) -> Path:
        if bugs is None:
            bugs = ["gcd", "flatten"]

        dataset_data = {
            "name": "test-dataset",
            "repository": "https://example.com/repo.git",
            "branch": "main",
            "language": "python",
            "test_command_template": "pytest test_{bug_id}.py",
            "bugs": [
                {"id": "gcd", "program": "p.py", "test": "t.py"},
                {"id": "flatten", "program": "p2.py", "test": "t2.py"},
            ],
        }
        datasets_dir = tmp_dir / "datasets"
        datasets_dir.mkdir(parents=True, exist_ok=True)
        dataset_path = datasets_dir / "test.yaml"
        dataset_path.write_text(yaml.dump(dataset_data), encoding="utf-8")

        batch_data = {
            "name": "test-batch",
            "dataset": "../datasets/test.yaml",
            "global": {
                "architecture": "mono_agent",
                "llm": {"model": "qwen3.5:9b"},
                "prompt_template": "Fix {bug_id}",
            },
            "bugs": bugs,
        }
        batches_dir = tmp_dir / "batches"
        batches_dir.mkdir(parents=True, exist_ok=True)
        batch_path = batches_dir / "test.yaml"
        batch_path.write_text(yaml.dump(batch_data), encoding="utf-8")
        return batch_path

    def test_load_batch_config(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            batch_path = self._create_test_files(Path(tmp_dir))
            config, dataset_path = load_batch_config(batch_path)
            self.assertEqual(config.name, "test-batch")
            self.assertTrue(dataset_path.exists())

    def test_expand_bugs_specific(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            batch_path = self._create_test_files(Path(tmp_dir), bugs=["gcd"])
            config, dataset_path = load_batch_config(batch_path)
            dataset = load_dataset_config(dataset_path)
            bugs = expand_bugs(config, dataset)
            self.assertEqual(len(bugs), 1)
            self.assertEqual(bugs[0].id, "gcd")

    def test_expand_bugs_all(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            batch_path = self._create_test_files(Path(tmp_dir), bugs=["all"])
            config, dataset_path = load_batch_config(batch_path)
            dataset = load_dataset_config(dataset_path)
            bugs = expand_bugs(config, dataset)
            self.assertEqual(len(bugs), 2)

    def test_expand_bugs_invalid_id(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            batch_path = self._create_test_files(Path(tmp_dir), bugs=["nonexistent"])
            config, dataset_path = load_batch_config(batch_path)
            dataset = load_dataset_config(dataset_path)
            with self.assertRaises(ValueError):
                expand_bugs(config, dataset)

    def test_expand_bugs_all_mixed_rejected_at_load(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            batch_path = self._create_test_files(Path(tmp_dir), bugs=["all", "gcd"])
            with self.assertRaises(ValueError):
                load_batch_config(batch_path)


class TestPrompt(unittest.TestCase):
    def test_generate_prompt_with_error(self):
        bug = BugEntry(id="gcd", program="python_programs/gcd.py", test="python_testcases/test_gcd.py")
        dataset = DatasetConfig(
            name="test",
            repository="https://example.com",
            branch="main",
            language="python",
            test_command_template="pytest test_{bug_id}.py",
            bugs=[bug],
        )
        result = generate_prompt(bug, dataset, "Fix {bug_id} in {program}: {error_output}", "test error")
        self.assertIn("gcd", result)
        self.assertIn("python_programs/gcd.py", result)
        self.assertIn("test error", result)

    def test_generate_prompt_without_error(self):
        bug = BugEntry(id="gcd", program="python_programs/gcd.py", test="python_testcases/test_gcd.py")
        dataset = DatasetConfig(
            name="test",
            repository="https://example.com",
            branch="main",
            language="python",
            test_command_template="pytest test_{bug_id}.py",
            bugs=[bug],
        )
        result = generate_prompt(bug, dataset, "Fix {bug_id}: {error_output}", None)
        self.assertIn("gcd", result)
        self.assertIn("(error output not available)", result)

    @patch("llm_autofix_agents.batch.prompt.subprocess.run")
    def test_capture_error_output_success(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="test output", stderr="")
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = capture_error_output(Path(tmp_dir), "pytest test.py", timeout_seconds=30)
        self.assertEqual(result, "test output")

    @patch("llm_autofix_agents.batch.prompt.subprocess.run")
    def test_capture_error_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=30)
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = capture_error_output(Path(tmp_dir), "pytest test.py", timeout_seconds=30)
        self.assertIsNone(result)

    @patch("llm_autofix_agents.batch.prompt.subprocess.run")
    def test_capture_error_truncates_long_output(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="a" * 10000, stderr="")
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = capture_error_output(Path(tmp_dir), "pytest test.py", timeout_seconds=30)
        self.assertTrue(len(result) <= 4000)


class TestSummary(unittest.TestCase):
    def test_new_batch_id(self):
        now = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)
        batch_id = new_batch_id("my-batch", now)
        self.assertEqual(batch_id, "batch-my-batch-20260501T120000Z")

    def test_bug_run_result(self):
        result = BugRunResult(bug_id="gcd", status="success", run_id="run-123")
        self.assertEqual(result.bug_id, "gcd")
        self.assertEqual(result.status, "success")

    def test_batch_summary_counts(self):
        results = [
            BugRunResult(bug_id="gcd", status="success", duration_seconds=10.0),
            BugRunResult(bug_id="flatten", status="failed", duration_seconds=20.0),
            BugRunResult(bug_id="mergesort", status="timed_out", duration_seconds=300.0),
        ]
        now = datetime.now(UTC)
        summary = BatchSummary(
            batch_name="test",
            config_path="test.yaml",
            dataset_name="quixbugs",
            architecture="mono_agent",
            model="qwen3.5:9b",
            provider="ollama",
            started_at=now,
            completed_at=now,
            total_bugs=3,
            successful=1,
            failed=1,
            timed_out=1,
            infra_failures=0,
            results=results,
        )
        self.assertEqual(summary.total_bugs, 3)
        self.assertEqual(summary.successful, 1)


class TestParseJsonOutput(unittest.TestCase):
    def test_valid_json(self):
        payload = {"output": {"status": "success", "identity": {"run_id": "run-123"}}}
        result = _parse_json_output(json.dumps(payload))
        self.assertEqual(result["output"]["status"], "success")

    def test_invalid_json(self):
        self.assertIsNone(_parse_json_output("not json"))

    def test_non_dict_json(self):
        self.assertIsNone(_parse_json_output("[1,2,3]"))


class TestTruncate(unittest.TestCase):
    def test_short_text(self):
        self.assertEqual(_truncate("short", 10), "short")

    def test_long_text(self):
        result = _truncate("a" * 100, 50)
        self.assertEqual(len(result), 53)
        self.assertTrue(result.endswith("..."))


if __name__ == "__main__":
    unittest.main()
