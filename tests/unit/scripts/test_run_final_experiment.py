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


class TestBuildValidationPrompt(unittest.TestCase):
    def test_contains_batch_dir_path(self) -> None:
        batch_dir = Path("/results/batch-experiment-mono-20260522T")
        prompt = rfe.build_validation_prompt(batch_dir)
        self.assertIn(str(batch_dir), prompt)

    def test_contains_repo_root(self) -> None:
        batch_dir = Path("/results/batch-experiment-mono-20260522T")
        prompt = rfe.build_validation_prompt(batch_dir)
        self.assertIn(str(rfe.REPO_ROOT), prompt)

    def test_mentions_apr_validator_skill(self) -> None:
        prompt = rfe.build_validation_prompt(Path("/some/batch"))
        self.assertIn("apr-validator", prompt)

    def test_mentions_batch_db(self) -> None:
        prompt = rfe.build_validation_prompt(Path("/some/batch"))
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


if __name__ == "__main__":
    unittest.main()
