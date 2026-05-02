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
    RepositoryConfig,
    TestConfig,
    expand_bugs,
    load_batch_config,
    load_dataset_config,
)
from llm_autofix_agents.batch.prompt import capture_error_output, generate_prompt
from llm_autofix_agents.batch.runner import _parse_json_output, _truncate
from llm_autofix_agents.batch.summary import BatchSummary, BugRunResult, new_batch_id
from llm_autofix_agents.contracts import RunArchitecture
from llm_autofix_agents.datasets.base import DatasetPreparationContext, PreparedExecutionCase
from llm_autofix_agents.datasets.bugsinpy import BugsInPyAdapter
from llm_autofix_agents.datasets.quixbugs import QuixBugsAdapter
from llm_autofix_agents.datasets.registry import available_types, get


def _make_quixbugs_dataset(**overrides) -> DatasetConfig:
    defaults = {
        "type": "quixbugs",
        "name": "test-quixbugs",
        "language": "python",
        "repository": {"url": "https://github.com/example/test.git", "branch": "main"},
        "test": {"command_template": "pytest test_{bug_id}.py"},
        "bugs": [{"id": "gcd", "program": "gcd.py", "test": "test_gcd.py"}],
    }
    defaults.update(overrides)
    return DatasetConfig(**defaults)


class TestBugEntry(unittest.TestCase):
    def test_valid_bug_entry_required_fields(self):
        bug = BugEntry(id="gcd")
        self.assertEqual(bug.id, "gcd")
        self.assertIsNone(bug.program)
        self.assertIsNone(bug.test)

    def test_bug_entry_with_optional_fields(self):
        bug = BugEntry(id="gcd", program="gcd.py", test="test_gcd.py")
        self.assertEqual(bug.program, "gcd.py")
        self.assertEqual(bug.test, "test_gcd.py")

    def test_bug_entry_with_test_command(self):
        bug = BugEntry(id="gcd", test_command="custom test command")
        self.assertEqual(bug.test_command, "custom test command")

    def test_bug_entry_with_metadata(self):
        bug = BugEntry(id="gcd", metadata={"project": "foo", "version": "0"})
        self.assertEqual(bug.metadata["project"], "foo")

    def test_bug_entry_strips_whitespace(self):
        bug = BugEntry(id=" gcd ", program=" gcd.py ", test=" test.py ")
        self.assertEqual(bug.id, "gcd")
        self.assertEqual(bug.program, "gcd.py")

    def test_bug_entry_rejects_empty_id(self):
        with self.assertRaises(ValueError):
            BugEntry(id="")

    def test_bug_entry_rejects_extra_fields(self):
        with self.assertRaises(ValueError):
            BugEntry(id="gcd", unknown_field="x")


class TestRepositoryConfig(unittest.TestCase):
    def test_valid_repository_config(self):
        repo = RepositoryConfig(url="https://github.com/example/repo.git", branch="main")
        self.assertEqual(repo.url, "https://github.com/example/repo.git")
        self.assertEqual(repo.branch, "main")

    def test_repository_config_without_branch(self):
        repo = RepositoryConfig(url="https://github.com/example/repo.git")
        self.assertIsNone(repo.branch)

    def test_repository_config_strips_whitespace(self):
        repo = RepositoryConfig(url="  https://github.com/example/repo.git  ", branch="  main  ")
        self.assertEqual(repo.url, "https://github.com/example/repo.git")
        self.assertEqual(repo.branch, "main")

    def test_repository_config_rejects_empty_url(self):
        with self.assertRaises(ValueError):
            RepositoryConfig(url="")


class TestTestConfig(unittest.TestCase):
    def test_valid_test_config(self):
        tc = TestConfig(command_template="pytest test_{bug_id}.py")
        self.assertEqual(tc.command_template, "pytest test_{bug_id}.py")


class TestDatasetConfig(unittest.TestCase):
    def _make_dataset_data(self, **overrides) -> dict:
        defaults = {
            "type": "quixbugs",
            "name": "test-dataset",
            "language": "python",
            "repository": {"url": "https://example.com/repo.git", "branch": "main"},
            "test": {"command_template": "pytest test_{bug_id}.py"},
            "bugs": [
                {"id": "gcd", "program": "p.py", "test": "t.py"},
                {"id": "flatten", "program": "p2.py", "test": "t2.py"},
            ],
        }
        defaults.update(overrides)
        return defaults

    def test_resolve_test_command_from_template(self):
        dataset = DatasetConfig(**self._make_dataset_data())
        bug = dataset.bugs[0]
        self.assertEqual(dataset.resolve_test_command(bug), "pytest test_gcd.py")

    def test_resolve_test_command_override(self):
        data = self._make_dataset_data()
        data["bugs"][0]["test_command"] = "custom command"
        dataset = DatasetConfig(**data)
        bug = dataset.bugs[0]
        self.assertEqual(dataset.resolve_test_command(bug), "custom command")

    def test_resolve_test_command_no_config_raises(self):
        data = self._make_dataset_data()
        del data["test"]
        del data["repository"]
        data["bugs"] = [{"id": "gcd"}]
        dataset = DatasetConfig(**data)
        bug = dataset.bugs[0]
        with self.assertRaises(ValueError):
            dataset.resolve_test_command(bug)

    def test_load_dataset_config_from_yaml(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data = {
                "type": "quixbugs",
                "name": "test-dataset",
                "language": "python",
                "repository": {"url": "https://example.com/repo.git", "branch": "main"},
                "test": {"command_template": "pytest test_{bug_id}.py"},
                "bugs": [
                    {"id": "gcd", "program": "p.py", "test": "t.py"},
                    {"id": "flatten", "program": "p2.py", "test": "t2.py"},
                ],
            }
            path = Path(tmp_dir) / "dataset.yaml"
            path.write_text(yaml.dump(data), encoding="utf-8")
            config = load_dataset_config(path)
            self.assertEqual(config.name, "test-dataset")
            self.assertEqual(config.type, "quixbugs")
            self.assertEqual(len(config.bugs), 2)
            self.assertEqual(config.bugs[0].id, "gcd")

    def test_dataset_config_with_tooling(self):
        data = self._make_dataset_data(
            type="bugsinpy",
            repository=None,
            test=None,
            tooling={
                "checkout_command_template": "bugsinpy-checkout -p {project}",
                "test_command": "bugsinpy-test",
            },
            bugs=[{"id": "bug-1", "metadata": {"project": "foo"}}],
        )
        dataset = DatasetConfig(**data)
        self.assertEqual(dataset.tooling["test_command"], "bugsinpy-test")


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
            "type": "quixbugs",
            "name": "test-dataset",
            "language": "python",
            "repository": {"url": "https://example.com/repo.git", "branch": "main"},
            "test": {"command_template": "pytest test_{bug_id}.py"},
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
        case = PreparedExecutionCase(
            case_id="gcd",
            dataset_name="test",
            dataset_type="quixbugs",
            host_workspace=Path("/tmp/ws"),
            container_workspace="/benchmark-workspaces/batch-1/gcd",
            test_command="pytest test_gcd.py",
            prompt_variables={"bug_id": "gcd", "program": "gcd.py", "test": "test_gcd.py"},
        )
        result = generate_prompt(case, "Fix {bug_id} in {program}: {error_output}", "test error")
        self.assertIn("gcd", result)
        self.assertIn("gcd.py", result)
        self.assertIn("test error", result)

    def test_generate_prompt_without_error(self):
        case = PreparedExecutionCase(
            case_id="gcd",
            dataset_name="test",
            dataset_type="quixbugs",
            host_workspace=Path("/tmp/ws"),
            container_workspace="/benchmark-workspaces/batch-1/gcd",
            test_command="pytest test_gcd.py",
            prompt_variables={"bug_id": "gcd", "program": "gcd.py", "test": "test_gcd.py"},
        )
        result = generate_prompt(case, "Fix {bug_id}: {error_output}", None)
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


class TestDatasetAdapterRegistry(unittest.TestCase):
    def test_registry_returns_quixbugs_adapter(self):
        adapter = get("quixbugs")
        self.assertIsInstance(adapter, QuixBugsAdapter)
        self.assertEqual(adapter.type, "quixbugs")

    def test_registry_returns_bugsinpy_adapter(self):
        adapter = get("bugsinpy")
        self.assertIsInstance(adapter, BugsInPyAdapter)
        self.assertEqual(adapter.type, "bugsinpy")

    def test_registry_raises_for_unknown_type(self):
        with self.assertRaises(ValueError):
            get("nonexistent")

    def test_available_types_includes_known_adapters(self):
        types = available_types()
        self.assertIn("quixbugs", types)
        self.assertIn("bugsinpy", types)


class TestQuixBugsAdapter(unittest.TestCase):
    def _make_context(self, **overrides) -> DatasetPreparationContext:
        dataset = _make_quixbugs_dataset()
        defaults = {
            "dataset": dataset,
            "batch": None,
            "batch_id": "batch-test-20260501",
            "host_workspace_root": Path("/tmp/benchmark-workspaces/batch-test"),
            "container_workspace_root": "/benchmark-workspaces/batch-test",
        }
        defaults.update(overrides)
        if defaults["batch"] is None:
            defaults["batch"] = GlobalSettings(
                architecture=RunArchitecture.MONO_AGENT,
                llm=LLMSettings(model="test"),
                prompt_template="Fix {bug_id}",
            )
        return DatasetPreparationContext(**defaults)

    @patch("llm_autofix_agents.datasets.quixbugs._shallow_clone")
    def test_prepare_case_creates_workspace(self, mock_clone):
        adapter = QuixBugsAdapter()
        dataset = _make_quixbugs_dataset()
        bug = dataset.bugs[0]
        context = self._make_context(dataset=dataset)

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_root = Path(tmp_dir)
            context = self._make_context(
                dataset=dataset,
                host_workspace_root=workspace_root,
                container_workspace_root="/benchmark-workspaces/batch-test",
            )
            mock_clone.return_value = None

            case = adapter.prepare_case(context, bug)

            self.assertEqual(case.case_id, "gcd")
            self.assertEqual(case.dataset_type, "quixbugs")
            self.assertEqual(case.runner_service, "runner")
            self.assertIn("bug_id", case.prompt_variables)
            self.assertEqual(case.prompt_variables["bug_id"], "gcd")
            self.assertIn("program", case.prompt_variables)
            self.assertIn("test_command", case.prompt_variables)
            self.assertEqual(case.host_workspace, workspace_root / "gcd")

    def test_prepare_case_requires_repository(self):
        adapter = QuixBugsAdapter()
        with tempfile.TemporaryDirectory() as tmp_dir:
            dataset_data = {
                "type": "quixbugs",
                "name": "test-no-repo",
                "language": "python",
                "test": {"command_template": "pytest test_{bug_id}.py"},
                "bugs": [{"id": "gcd"}],
            }
            dataset = DatasetConfig(**dataset_data)
            bug = dataset.bugs[0]
            context = DatasetPreparationContext(
                dataset=dataset,
                batch=GlobalSettings(
                    architecture=RunArchitecture.MONO_AGENT,
                    llm=LLMSettings(model="test"),
                    prompt_template="Fix {bug_id}",
                ),
                batch_id="batch-test",
                host_workspace_root=Path(tmp_dir),
                container_workspace_root="/benchmark-workspaces/batch-test",
            )
            with self.assertRaises(ValueError):
                adapter.prepare_case(context, bug)


class TestBugsInPyAdapter(unittest.TestCase):
    @patch("llm_autofix_agents.datasets.bugsinpy.subprocess.run")
    def test_prepare_case_with_checkout(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        adapter = BugsInPyAdapter()
        dataset = DatasetConfig(
            type="bugsinpy",
            name="test-bugsinpy",
            language="python",
            tooling={
                "checkout_command_template": (
                    "bugsinpy-checkout -p {project} -i {bug_id} "
                    "-v {version} -w {container_workspace}"
                ),
                "compile_command": "bugsinpy-compile",
                "test_command": "bugsinpy-test",
            },
            bugs=[
                BugEntry(
                    id="youtube-dl-2",
                    program="youtube-dl",
                    metadata={"project": "youtube-dl", "bug_id": "2", "version": "0"},
                ),
            ],
        )
        bug = dataset.bugs[0]

        with tempfile.TemporaryDirectory() as tmp_dir:
            context = DatasetPreparationContext(
                dataset=dataset,
                batch=GlobalSettings(
                    architecture=RunArchitecture.MONO_AGENT,
                    llm=LLMSettings(model="test"),
                    prompt_template="Fix {bug_id}",
                ),
                batch_id="batch-test",
                host_workspace_root=Path(tmp_dir),
                container_workspace_root="/benchmark-workspaces/batch-test",
            )
            case = adapter.prepare_case(context, bug)

            self.assertEqual(case.case_id, "youtube-dl-2")
            self.assertEqual(case.dataset_type, "bugsinpy")
            self.assertEqual(case.test_command, "bugsinpy-test")
            self.assertEqual(case.runner_service, "bugsinpy-runner")
            self.assertIn("project", case.prompt_variables)
            self.assertEqual(case.prompt_variables["project"], "youtube-dl")

            # Verify docker compose was called for checkout and compile
            self.assertEqual(mock_run.call_count, 2)
            checkout_call = mock_run.call_args_list[0]
            self.assertIn("bugsinpy-runner", checkout_call[0][0])
            self.assertIn("bugsinpy-checkout", checkout_call[0][0][-1])

    @patch("llm_autofix_agents.datasets.bugsinpy.subprocess.run")
    def test_prepare_case_checkout_failure(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="checkout failed"
        )

        adapter = BugsInPyAdapter()
        dataset = DatasetConfig(
            type="bugsinpy",
            name="test-bugsinpy",
            language="python",
            tooling={
                "checkout_command_template": "bugsinpy-checkout -p {project}",
            },
            bugs=[BugEntry(id="test-bug", metadata={"project": "test"})],
        )
        bug = dataset.bugs[0]

        with tempfile.TemporaryDirectory() as tmp_dir:
            context = DatasetPreparationContext(
                dataset=dataset,
                batch=GlobalSettings(
                    architecture=RunArchitecture.MONO_AGENT,
                    llm=LLMSettings(model="test"),
                    prompt_template="Fix {bug_id}",
                ),
                batch_id="batch-test",
                host_workspace_root=Path(tmp_dir),
                container_workspace_root="/benchmark-workspaces/batch-test",
            )
            with self.assertRaises(RuntimeError):
                adapter.prepare_case(context, bug)


class TestPreparedExecutionCase(unittest.TestCase):
    def test_case_is_frozen(self):
        case = PreparedExecutionCase(
            case_id="gcd",
            dataset_name="test",
            dataset_type="quixbugs",
            host_workspace=Path("/tmp/ws"),
            container_workspace="/benchmark-workspaces/batch-1/gcd",
            test_command="pytest test_gcd.py",
            prompt_variables={"bug_id": "gcd"},
        )
        with self.assertRaises(AttributeError):
            case.case_id = "other"

    def test_case_default_runner_service(self):
        case = PreparedExecutionCase(
            case_id="gcd",
            dataset_name="test",
            dataset_type="quixbugs",
            host_workspace=Path("/tmp/ws"),
            container_workspace="/benchmark-workspaces/batch-1/gcd",
            test_command="pytest test_gcd.py",
            prompt_variables={"bug_id": "gcd"},
        )
        self.assertEqual(case.runner_service, "runner")

    def test_case_custom_runner_service(self):
        case = PreparedExecutionCase(
            case_id="gcd",
            dataset_name="test",
            dataset_type="bugsinpy",
            host_workspace=Path("/tmp/ws"),
            container_workspace="/benchmark-workspaces/batch-1/gcd",
            test_command="bugsinpy-test",
            prompt_variables={"bug_id": "gcd"},
            runner_service="bugsinpy-runner",
        )
        self.assertEqual(case.runner_service, "bugsinpy-runner")


class TestRepoSourceLocalPath(unittest.TestCase):
    def test_prepare_local_directory(self):
        from llm_autofix_agents.repo_source import PreparedRepository, prepare_target_repository

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = prepare_target_repository(repository=tmp_dir)
            self.assertIsInstance(result, PreparedRepository)
            self.assertEqual(result.path, Path(tmp_dir).resolve())
            self.assertFalse(result.temporary)
            result.cleanup()

    def test_prepare_remote_requires_branch(self):
        from llm_autofix_agents.repo_source import prepare_target_repository

        with self.assertRaises(ValueError):
            prepare_target_repository(repository="https://github.com/example/repo.git")

    @patch("llm_autofix_agents.repo_source.subprocess.run")
    def test_prepare_remote_with_branch(self, mock_run):
        from llm_autofix_agents.repo_source import prepare_target_repository

        mock_run.return_value = subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr="")
        result = prepare_target_repository(repository="https://github.com/example/repo.git", branch="main")
        self.assertTrue(result.temporary)
        result.cleanup()


if __name__ == "__main__":
    unittest.main()
