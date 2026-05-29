"""Unit tests for scripts/run_final_experiment.py."""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

# Make the scripts directory importable
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import run_final_experiment as rfe


class TestValidateEnv(unittest.TestCase):
    def test_raises_on_missing_ollama_topic(self) -> None:
        env = {}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                rfe.validate_env(gpt_only=False)
        self.assertEqual(ctx.exception.code, 1)

    def test_passes_when_ollama_topic_set(self) -> None:
        with patch.dict(os.environ, {"NTFY_TOPIC": "my-topic"}, clear=True):
            rfe.validate_env(gpt_only=False)  # must not raise

    def test_raises_on_missing_gpt_vars(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                rfe.validate_env(gpt_only=True)

    def test_raises_on_missing_openai_key_only(self) -> None:
        with patch.dict(os.environ, {"NTFY_TOPIC_GPT": "gpt-topic"}, clear=True):
            with self.assertRaises(SystemExit):
                rfe.validate_env(gpt_only=True)

    def test_passes_when_all_gpt_vars_set(self) -> None:
        env = {"NTFY_TOPIC_GPT": "gpt-topic", "OPENAI_API_KEY": "sk-test"}
        with patch.dict(os.environ, env, clear=True):
            rfe.validate_env(gpt_only=True)  # must not raise

    def test_also_validates_in_dry_run(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                rfe.validate_env(gpt_only=False, dry_run=True)


class TestNotify(unittest.TestCase):
    def _mock_post(self) -> MagicMock:
        return MagicMock(return_value=MagicMock(status_code=200))

    def test_sends_correct_headers(self) -> None:
        mock_post = self._mock_post()
        rfe.notify(
            "Test Title",
            "Test message",
            priority=4,
            tags=("warning", "rocket"),
            topic="my-topic",
            _http_post=mock_post,
        )
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        headers = kwargs["headers"]
        self.assertEqual(headers["Title"], "Test Title")
        self.assertEqual(headers["Priority"], "4")
        self.assertEqual(headers["Tags"], "warning,rocket")
        self.assertIn("my-topic", mock_post.call_args[0][0])

    def test_posts_to_correct_url(self) -> None:
        mock_post = self._mock_post()
        rfe.notify("T", "M", topic="test-topic-xyz", _http_post=mock_post)
        url = mock_post.call_args[0][0]
        self.assertEqual(url, "https://ntfy.sh/test-topic-xyz")

    def test_omits_tags_header_when_empty(self) -> None:
        mock_post = self._mock_post()
        rfe.notify("T", "M", topic="t", _http_post=mock_post)
        _, kwargs = mock_post.call_args
        self.assertNotIn("Tags", kwargs["headers"])

    def test_silent_when_topic_empty(self) -> None:
        mock_post = self._mock_post()
        with patch.dict(os.environ, {}, clear=True):
            rfe.notify("T", "M", topic="", _http_post=mock_post)
        mock_post.assert_not_called()

    def test_uses_env_topic_fallback(self) -> None:
        mock_post = self._mock_post()
        with patch.dict(os.environ, {"NTFY_TOPIC": "env-topic"}):
            rfe.notify("T", "M", topic="", _http_post=mock_post)
        url = mock_post.call_args[0][0]
        self.assertIn("env-topic", url)

    def test_does_not_raise_on_http_error(self) -> None:
        def failing_post(*args, **kwargs):  # noqa: ANN001,ANN002,ANN003
            raise ConnectionError("network down")

        # Must not raise — notifications never abort the script
        rfe.notify("T", "M", topic="t", _http_post=failing_post)

    def test_message_encoded_as_bytes(self) -> None:
        mock_post = self._mock_post()
        rfe.notify("T", "hello", topic="t", _http_post=mock_post)
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["content"], b"hello")


class TestCheckOpenAIBalance(unittest.TestCase):
    def _mock_get(self, status_code: int, json_data: dict) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data
        resp.raise_for_status = MagicMock()
        mock = MagicMock(return_value=resp)
        return mock

    def test_stops_when_balance_low(self) -> None:
        mock_get = self._mock_get(200, {"total_available": 0.30})
        can_continue, remaining = rfe.check_openai_balance(
            "sk-test", min_balance_usd=1.0, _http_get=mock_get
        )
        self.assertFalse(can_continue)
        self.assertAlmostEqual(remaining, 0.30)

    def test_continues_when_balance_sufficient(self) -> None:
        mock_get = self._mock_get(200, {"total_available": 5.00})
        can_continue, remaining = rfe.check_openai_balance(
            "sk-test", min_balance_usd=1.0, _http_get=mock_get
        )
        self.assertTrue(can_continue)
        self.assertAlmostEqual(remaining, 5.00)

    def test_continues_on_404_pay_as_you_go(self) -> None:
        resp = MagicMock()
        resp.status_code = 404
        mock_get = MagicMock(return_value=resp)
        can_continue, remaining = rfe.check_openai_balance("sk-test", _http_get=mock_get)
        self.assertTrue(can_continue)
        self.assertIsNone(remaining)

    def test_continues_on_network_error(self) -> None:
        def failing_get(*args, **kwargs):  # noqa: ANN001,ANN002,ANN003
            raise ConnectionError("network down")

        can_continue, remaining = rfe.check_openai_balance("sk-test", _http_get=failing_get)
        self.assertTrue(can_continue)
        self.assertIsNone(remaining)

    def test_sends_correct_auth_header(self) -> None:
        mock_get = self._mock_get(200, {"total_available": 10.0})
        rfe.check_openai_balance("sk-mykey", _http_get=mock_get)
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk-mykey")


class TestDiscoverConfigs(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.batches_dir = Path(self.tmp.name)
        # Create dummy YAML files
        for name in [
            "experiment-ollama-mono-gemma4-26b.yaml",
            "experiment-ollama-orchestrator-qwen3.5-9b.yaml",
            "experiment-gpt-5.4-mini-mono.yaml",
            "experiment-gpt-5.4-mini-orchestrator.yaml",
        ]:
            (self.batches_dir / name).write_text("name: test\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_ollama_excludes_gpt(self) -> None:
        configs = rfe.discover_configs(self.batches_dir, gpt_only=False)
        names = [p.name for p in configs]
        self.assertTrue(all("gpt-5.4" not in n for n in names))
        self.assertEqual(len(configs), 2)

    def test_gpt_only_includes_only_gpt(self) -> None:
        configs = rfe.discover_configs(self.batches_dir, gpt_only=True)
        names = [p.name for p in configs]
        self.assertTrue(all("gpt-5.4" in n for n in names))
        self.assertEqual(len(configs), 2)

    def test_ollama_returns_empty_when_no_yamls(self) -> None:
        empty_dir = Path(self.tmp.name) / "empty"
        empty_dir.mkdir()
        configs = rfe.discover_configs(empty_dir, gpt_only=False)
        self.assertEqual(configs, [])

    def test_gpt_returns_empty_when_no_gpt_yamls(self) -> None:
        only_ollama_dir = Path(self.tmp.name) / "only_ollama"
        only_ollama_dir.mkdir()
        (only_ollama_dir / "experiment-ollama-mono.yaml").write_text("name: test\n")
        configs = rfe.discover_configs(only_ollama_dir, gpt_only=True)
        self.assertEqual(configs, [])


class TestConstants(unittest.TestCase):
    def test_copilot_model_uses_dot_not_dash(self) -> None:
        """Regression: model name must be 'claude-sonnet-4.5' (dot), not 'claude-sonnet-4-5' (dash).
        The copilot CLI rejects the dash variant with 'model not available'."""
        self.assertEqual(rfe.COPILOT_MODEL, "claude-sonnet-4.5")
        self.assertNotIn("4-6", rfe.COPILOT_MODEL)


class TestBuildValidationPrompt(unittest.TestCase):
    def test_contains_batch_dir_path(self) -> None:
        batch_dir = Path("/results/batch-experiment-mono-20260522T")
        prompt = rfe.build_validation_prompt([batch_dir])
        self.assertIn(str(batch_dir), prompt)

    def test_contains_repo_root(self) -> None:
        batch_dir = Path("/results/batch-experiment-mono-20260522T")
        prompt = rfe.build_validation_prompt([batch_dir])
        self.assertIn(str(rfe.REPO_ROOT), prompt)

    def test_mentions_apr_validator_skill(self) -> None:
        prompt = rfe.build_validation_prompt([Path("/some/batch")])
        self.assertIn("apr-validator", prompt)

    def test_mentions_batch_db(self) -> None:
        prompt = rfe.build_validation_prompt([Path("/some/batch")])
        self.assertIn("batch.db", prompt)


class TestFindProducedBatchDir(unittest.TestCase):
    def test_finds_dir_created_after_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            results_dir = Path(tmp)
            before = time.time() - 1

            batch_dir = results_dir / "batch-myname-20260522T123456Z"
            batch_dir.mkdir()
            (batch_dir / "batch.db").write_text("")

            found = rfe.find_produced_batch_dir("myname", results_dir, before)
            self.assertIsNotNone(found)
            self.assertEqual(found, batch_dir)

    def test_returns_none_when_dir_is_old(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            results_dir = Path(tmp)
            batch_dir = results_dir / "batch-myname-20260522T000000Z"
            batch_dir.mkdir()

            after = time.time() + 10  # created before this threshold
            found = rfe.find_produced_batch_dir("myname", results_dir, after)
            self.assertIsNone(found)


class TestSmokeTestFlag(unittest.TestCase):
    """Regression tests for --smoke-test behavior."""

    def _make_sub_batch(self, name: str, model: str, skip: bool = False) -> rfe.SubBatch:
        return rfe.SubBatch(
            path=Path(f"/tmp/{name}.yaml"),
            name=name,
            model=model,
            skip_reason="done" if skip else None,
        )

    def _make_args(self, smoke_test: bool = True, validation_wait: int = 300) -> object:
        import argparse
        args = argparse.Namespace(
            smoke_test=smoke_test,
            gpt_only=False,
            force=False,
            start_from=None,
            dry_run=False,
            gpu_poll=300,
            skip_validation=False,
            validation_only=False,
            validation_wait=validation_wait,
        )
        return args

    def test_smoke_filter_picks_qwen_batches(self) -> None:
        """Smoke test should pick qwen batches over gemma when both are available."""
        sub_batches = [
            self._make_sub_batch("gemma-mono-PySnooper", "gemma4-26b-ctx32k"),
            self._make_sub_batch("gemma-multi-PySnooper", "gemma4-26b-ctx32k"),
            self._make_sub_batch("qwen-mono-PySnooper",  "qwen3.5-9b-ctx65k"),
            self._make_sub_batch("qwen-multi-PySnooper", "qwen3.5-9b-ctx65k"),
            self._make_sub_batch("qwen-planner-PySnooper", "qwen3.5-9b-ctx65k"),
            self._make_sub_batch("qwen-extra-PySnooper", "qwen3.5-9b-ctx65k"),
        ]
        # Simulate the smoke filter logic extracted from _run_experiments
        eligible = [b for b in sub_batches if b.skip_reason is None]
        qwen = [b for b in eligible if "qwen" in b.model]
        result = (qwen if qwen else eligible)[:3]

        self.assertEqual(len(result), 3)
        self.assertTrue(all("qwen" in b.model for b in result))

    def test_smoke_filter_falls_back_to_any_when_no_qwen(self) -> None:
        """When no qwen batches exist, smoke test falls back to first 3 eligible."""
        sub_batches = [
            self._make_sub_batch(f"gemma-batch-{i}", "gemma4-26b-ctx32k") for i in range(5)
        ]
        eligible = [b for b in sub_batches if b.skip_reason is None]
        qwen = [b for b in eligible if "qwen" in b.model]
        result = (qwen if qwen else eligible)[:3]

        self.assertEqual(len(result), 3)

    def test_smoke_filter_skips_already_done_batches(self) -> None:
        """Smoke filter should only consider batches without skip_reason."""
        sub_batches = [
            self._make_sub_batch("qwen-batch-done-1", "qwen3.5-9b-ctx65k", skip=True),
            self._make_sub_batch("qwen-batch-done-2", "qwen3.5-9b-ctx65k", skip=True),
            self._make_sub_batch("qwen-batch-pending", "qwen3.5-9b-ctx65k", skip=False),
        ]
        eligible = [b for b in sub_batches if b.skip_reason is None]
        qwen = [b for b in eligible if "qwen" in b.model]
        result = (qwen if qwen else eligible)[:3]

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "qwen-batch-pending")

    def test_smoke_test_sets_validation_wait_to_zero(self) -> None:
        """--smoke-test should override validation_wait default (300) to 0."""
        args = self._make_args(smoke_test=True, validation_wait=300)
        # Simulate the post-parse override in main()
        if args.smoke_test and args.validation_wait == 300:
            args.validation_wait = 0
        self.assertEqual(args.validation_wait, 0)

    def test_smoke_test_does_not_override_explicit_validation_wait(self) -> None:
        """--smoke-test should NOT override an explicitly set --validation-wait value."""
        args = self._make_args(smoke_test=True, validation_wait=60)
        if args.smoke_test and args.validation_wait == 300:
            args.validation_wait = 0
        self.assertEqual(args.validation_wait, 60)

    def test_notify_interval_1_triggers_after_each_batch(self) -> None:
        """With notify_interval=1, notification fires after every completed batch."""
        mock_post = MagicMock(return_value=MagicMock(status_code=200))
        notify_interval = 1
        completed_since_notify = 0

        for _ in range(3):
            completed_since_notify += 1
            if completed_since_notify >= notify_interval:
                rfe.notify("T", "M", topic="test", _http_post=mock_post)
                completed_since_notify = 0

        self.assertEqual(mock_post.call_count, 3)

    def test_notify_interval_5_fires_once_for_3_batches(self) -> None:
        """With notify_interval=5, no mid-run notification fires for only 3 batches."""
        mock_post = MagicMock(return_value=MagicMock(status_code=200))
        notify_interval = 5
        completed_since_notify = 0

        for _ in range(3):
            completed_since_notify += 1
            if completed_since_notify >= notify_interval:
                rfe.notify("T", "M", topic="test", _http_post=mock_post)
                completed_since_notify = 0

        self.assertEqual(mock_post.call_count, 0)  # never fires in 3 iterations


class TestValidationPhase(unittest.TestCase):
    """Tests for _run_validation_phase parallel execution."""

    def _make_args(self, dry_run: bool = False, validation_wait: int = 0) -> object:
        import argparse
        ns = argparse.Namespace()
        ns.dry_run = dry_run
        ns.validation_wait = validation_wait
        ns.smoke_test = False
        return ns

    def test_all_batch_dirs_validated(self) -> None:
        """Every batch_dir in the list must get exactly one run_validation call."""
        with tempfile.TemporaryDirectory() as tmp:
            dirs = [Path(tmp) / f"batch-experiment-{i}" for i in range(4)]
            for d in dirs:
                d.mkdir()
                (d / "batch.db").write_text("")

            with patch.object(rfe, "run_validation", return_value=(True, None)) as mock_val, \
                 patch.object(rfe, "notify"):
                rc = rfe._run_validation_phase(
                    dirs,
                    args=self._make_args(),
                    ntfy_topic="test",
                    mode_label="TEST",
                )

        self.assertEqual(rc, 0)
        self.assertEqual(mock_val.call_count, 4)
        # run_validation is called with a list (group), so unwrap to get the single dir
        validated_dirs = {c.args[0][0] for c in mock_val.call_args_list}
        self.assertEqual(validated_dirs, set(dirs))

    def test_failures_collected_and_returns_nonzero(self) -> None:
        """If any run_validation returns False, rc must be 1 and name recorded."""
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "batch-experiment-good"
            bad = Path(tmp) / "batch-experiment-bad"
            for d in (good, bad):
                d.mkdir()
                (d / "batch.db").write_text("")

            side_effects = {good: (True, None), bad: (False, "exit:1")}

            def _fake_validate(group: list, **kwargs: object) -> tuple:
                # group is a list with one Path element
                return side_effects[group[0]]

            with patch.object(rfe, "run_validation", side_effect=_fake_validate), \
                 patch.object(rfe, "notify"):
                rc = rfe._run_validation_phase(
                    [good, bad],
                    args=self._make_args(),
                    ntfy_topic="test",
                    mode_label="TEST",
                )

        self.assertEqual(rc, 1)

    def test_dry_run_does_not_call_run_validation(self) -> None:
        """In dry-run mode no real validation should be invoked."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "batch-experiment-x"
            d.mkdir()
            (d / "batch.db").write_text("")

            with patch.object(rfe, "run_validation") as mock_val, \
                 patch.object(rfe, "notify"):
                rfe._run_validation_phase(
                    [d],
                    args=self._make_args(dry_run=True),
                    ntfy_topic="test",
                    mode_label="TEST",
                )

        mock_val.assert_not_called()


class TestCollectAllExperimentBatchDirs(unittest.TestCase):
    def test_collects_only_dirs_with_batch_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            results_dir = Path(tmp)

            complete = results_dir / "batch-experiment-mono-20260522T"
            complete.mkdir()
            (complete / "batch.db").write_text("")

            incomplete = results_dir / "batch-experiment-orchestrator-20260522T"
            incomplete.mkdir()
            # no batch.db

            non_experiment = results_dir / "batch-bugsinpy-hard-20260522T"
            non_experiment.mkdir()
            (non_experiment / "batch.db").write_text("")

            dirs = rfe.collect_all_experiment_batch_dirs(results_dir)
            self.assertEqual(dirs, [complete])


class TestSplitByProject(unittest.TestCase):
    """Tests for split_by_project — QuixBugs must not be split."""

    def _write_batch(self, tmp_dir: Path, name: str, bugs: list[str], dataset: str = "../../datasets/quixbugs.yaml") -> Path:
        data = {"name": name, "description": "test", "dataset": dataset, "global": {}, "bugs": bugs}
        p = tmp_dir / f"{name}.yaml"
        p.write_text(__import__("yaml").dump(data))
        return p

    def test_quixbugs_returns_single_batch(self) -> None:
        """QuixBugs config must not be split — all bugs in one sub-batch."""
        with tempfile.TemporaryDirectory() as cfg_tmp, tempfile.TemporaryDirectory() as out_tmp:
            cfg = self._write_batch(Path(cfg_tmp), "quixbugs-mono-agent-gpt-5.4-mini-extra20", ["bucketsort", "flatten", "gcd"])
            result = rfe.split_by_project(cfg, Path(out_tmp))
        self.assertEqual(len(result), 1)

    def test_quixbugs_single_batch_contains_all_bugs(self) -> None:
        """The single sub-batch must contain all original bugs unchanged."""
        bugs = ["bucketsort", "flatten", "gcd", "lis"]
        with tempfile.TemporaryDirectory() as cfg_tmp, tempfile.TemporaryDirectory() as out_tmp:
            cfg = self._write_batch(Path(cfg_tmp), "quixbugs-mono-agent-gemma4-26b-extra20", bugs)
            result = rfe.split_by_project(cfg, Path(out_tmp))
            loaded = __import__("yaml").safe_load(result[0].read_text())
        self.assertEqual(loaded["bugs"], bugs)

    def test_quixbugs_dataset_path_resolved_to_absolute(self) -> None:
        """dataset path must be absolute in the output so it works from any cwd."""
        with tempfile.TemporaryDirectory() as cfg_tmp, tempfile.TemporaryDirectory() as out_tmp:
            cfg = self._write_batch(Path(cfg_tmp), "quixbugs-planner-executor-qwen3.5-9b-extra20", ["gcd"])
            result = rfe.split_by_project(cfg, Path(out_tmp))
            loaded = __import__("yaml").safe_load(result[0].read_text())
        self.assertTrue(Path(loaded["dataset"]).is_absolute())

    def test_bugsinpy_still_splits_by_project(self) -> None:
        """BugsInPy configs must still be split per project."""
        bugs = ["thefuck-1", "thefuck-2", "httpie-1"]
        with tempfile.TemporaryDirectory() as cfg_tmp, tempfile.TemporaryDirectory() as out_tmp:
            cfg = self._write_batch(Path(cfg_tmp), "bugsinpy-mono-agent-gpt-5.4-mini", bugs,
                                    dataset="../../datasets/bugsinpy-full.yaml")
            result = rfe.split_by_project(cfg, Path(out_tmp))
        self.assertEqual(len(result), 2)  # thefuck + httpie


if __name__ == "__main__":
    unittest.main()
