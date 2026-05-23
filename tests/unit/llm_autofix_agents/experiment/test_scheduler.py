"""
Unit tests for llm_autofix_agents.experiment.scheduler.

All I/O functions (nvidia-smi, Ollama HTTP) are mocked; the scheduling
logic is tested as pure functions.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import subprocess
import tempfile

from llm_autofix_agents.experiment.scheduler import (
    DEFAULT_MODEL_VRAM_MIB,
    VRAM_SAFETY_BUFFER_MIB,
    SubBatch,
    can_run_model,
    get_free_vram_mib,
    get_ollama_loaded_vram_mib,
    get_ollama_model_sizes_mib,
    select_next_batch,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GEMMA = "gemma4-26b-ctx32k"
QWEN = "qwen3.5-9b-ctx65k"

# Small, round VRAM table used throughout tests to keep arithmetic obvious.
TEST_VRAM: dict[str, int] = {
    GEMMA: 18_000,
    QWEN:  6_000,
}
BUFFER = 1_000  # MiB, overrides default in calls that accept it


def _sub(model: str, name: str = "batch-x") -> SubBatch:
    return SubBatch(path=Path("/tmp/fake.yaml"), name=name, model=model)


# ---------------------------------------------------------------------------
# get_free_vram_mib
# ---------------------------------------------------------------------------


class TestGetFreeVramMib(unittest.TestCase):

    def _mock_run(self, stdout: str, returncode: int = 0) -> MagicMock:
        mock = MagicMock()
        mock.returncode = returncode
        mock.stdout = stdout
        return mock

    @patch("llm_autofix_agents.experiment.scheduler.subprocess.run")
    def test_success_single_gpu(self, mock_run: MagicMock) -> None:
        mock_run.return_value = self._mock_run("18432\n")
        result = get_free_vram_mib()
        self.assertEqual(result, 18432)

    @patch("llm_autofix_agents.experiment.scheduler.subprocess.run")
    def test_success_multiple_gpus_returns_minimum(self, mock_run: MagicMock) -> None:
        # Two GPUs: 20000 MiB and 15000 MiB free — return the bottleneck
        mock_run.return_value = self._mock_run("20000\n15000\n")
        result = get_free_vram_mib()
        self.assertEqual(result, 15000)

    @patch("llm_autofix_agents.experiment.scheduler.subprocess.run")
    def test_nonzero_returncode_returns_none(self, mock_run: MagicMock) -> None:
        # NVML version mismatch → exit code 18
        mock_run.return_value = self._mock_run("", returncode=18)
        result = get_free_vram_mib()
        self.assertIsNone(result)

    @patch(
        "llm_autofix_agents.experiment.scheduler.subprocess.run",
        side_effect=FileNotFoundError("nvidia-smi not found"),
    )
    def test_file_not_found_returns_none(self, _mock: MagicMock) -> None:
        result = get_free_vram_mib()
        self.assertIsNone(result)

    @patch(
        "llm_autofix_agents.experiment.scheduler.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=10),
    )
    def test_timeout_returns_none(self, _mock: MagicMock) -> None:
        result = get_free_vram_mib()
        self.assertIsNone(result)

    @patch("llm_autofix_agents.experiment.scheduler.subprocess.run")
    def test_empty_output_returns_none(self, mock_run: MagicMock) -> None:
        mock_run.return_value = self._mock_run("")
        result = get_free_vram_mib()
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# get_ollama_loaded_vram_mib
# ---------------------------------------------------------------------------


class TestGetOllamaLoadedVramMib(unittest.TestCase):

    def _mock_urlopen(self, payload: dict):
        """Context-manager mock for urlopen that returns JSON bytes."""
        raw = json.dumps(payload).encode()
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=raw)))
        mock_cm.__exit__ = MagicMock(return_value=False)
        return mock_cm

    @patch("llm_autofix_agents.experiment.scheduler.urlopen")
    def test_single_model_converts_bytes_to_mib(self, mock_urlopen: MagicMock) -> None:
        # 19 640 302 720 bytes ≈ 18 731 MiB
        mock_urlopen.return_value = self._mock_urlopen(
            {"models": [{"name": GEMMA, "size": 19_640_302_720}]}
        )
        result = get_ollama_loaded_vram_mib()
        self.assertEqual(result, 19_640_302_720 // (1024 * 1024))

    @patch("llm_autofix_agents.experiment.scheduler.urlopen")
    def test_multiple_models_sums_sizes(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = self._mock_urlopen(
            {
                "models": [
                    {"name": GEMMA, "size": 1024 * 1024 * 1000},
                    {"name": QWEN,  "size": 1024 * 1024 * 500},
                ]
            }
        )
        result = get_ollama_loaded_vram_mib()
        self.assertEqual(result, 1500)

    @patch("llm_autofix_agents.experiment.scheduler.urlopen")
    def test_no_models_returns_zero(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = self._mock_urlopen({"models": []})
        result = get_ollama_loaded_vram_mib()
        self.assertEqual(result, 0)

    @patch(
        "llm_autofix_agents.experiment.scheduler.urlopen",
        side_effect=OSError("connection refused"),
    )
    def test_connection_error_returns_zero(self, _mock: MagicMock) -> None:
        result = get_ollama_loaded_vram_mib()
        self.assertEqual(result, 0)


# ---------------------------------------------------------------------------
# get_ollama_model_sizes_mib
# ---------------------------------------------------------------------------


class TestGetOllamaModelSizesMib(unittest.TestCase):

    def _mock_urlopen(self, payload: dict):
        raw = json.dumps(payload).encode()
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=raw)))
        mock_cm.__exit__ = MagicMock(return_value=False)
        return mock_cm

    @patch("llm_autofix_agents.experiment.scheduler.urlopen")
    def test_returns_name_to_mib_dict(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = self._mock_urlopen(
            {
                "models": [
                    {"name": GEMMA, "size": 1024 * 1024 * 18_000},
                    {"name": QWEN,  "size": 1024 * 1024 * 6_000},
                ]
            }
        )
        result = get_ollama_model_sizes_mib()
        self.assertEqual(result, {GEMMA: 18_000, QWEN: 6_000})

    @patch("llm_autofix_agents.experiment.scheduler.urlopen")
    def test_strips_latest_tag_from_model_names(self, mock_urlopen: MagicMock) -> None:
        """Models with no explicit tag are stored as name:latest in Ollama.
        The scheduler must normalise them so they match YAML model fields."""
        mock_urlopen.return_value = self._mock_urlopen(
            {"models": [{"name": "gemma4-26b-ctx32k:latest", "size": 1024 * 1024 * 19_453}]}
        )
        result = get_ollama_model_sizes_mib()
        self.assertIn("gemma4-26b-ctx32k", result)
        self.assertNotIn("gemma4-26b-ctx32k:latest", result)
        self.assertEqual(result["gemma4-26b-ctx32k"], 19_453)

    @patch("llm_autofix_agents.experiment.scheduler.urlopen")
    def test_preserves_explicit_non_latest_tags(self, mock_urlopen: MagicMock) -> None:
        """Models with explicit meaningful tags (e.g. gemma4:26b) are not modified."""
        mock_urlopen.return_value = self._mock_urlopen(
            {"models": [{"name": "gemma4:26b", "size": 1024 * 1024 * 17_000}]}
        )
        result = get_ollama_model_sizes_mib()
        self.assertIn("gemma4:26b", result)
        self.assertEqual(result["gemma4:26b"], 17_000)

    @patch(
        "llm_autofix_agents.experiment.scheduler.urlopen",
        side_effect=OSError("timeout"),
    )
    def test_error_returns_empty_dict(self, _mock: MagicMock) -> None:
        result = get_ollama_model_sizes_mib()
        self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# can_run_model
# ---------------------------------------------------------------------------


class TestCanRunModel(unittest.TestCase):

    def test_sufficient_free_vram(self) -> None:
        # 20 000 free, 0 loaded, need 18 000 + 1 000 buffer = 19 000 → fits
        self.assertTrue(
            can_run_model(GEMMA, free_mib=20_000, ollama_loaded_mib=0,
                          model_vram_mib=TEST_VRAM, safety_buffer_mib=BUFFER)
        )

    def test_model_already_loaded_in_ollama(self) -> None:
        # free=2 000, ollama=18 000 (gemma loaded), effective=20 000 ≥ 19 000
        self.assertTrue(
            can_run_model(GEMMA, free_mib=2_000, ollama_loaded_mib=18_000,
                          model_vram_mib=TEST_VRAM, safety_buffer_mib=BUFFER)
        )

    def test_insufficient_even_with_ollama_vram(self) -> None:
        # free=2 000, ollama=6 000, effective=8 000 < 18 000 + 1 000
        self.assertFalse(
            can_run_model(GEMMA, free_mib=2_000, ollama_loaded_mib=6_000,
                          model_vram_mib=TEST_VRAM, safety_buffer_mib=BUFFER)
        )

    def test_exactly_at_threshold(self) -> None:
        # effective_free == required + buffer → should pass
        required = TEST_VRAM[GEMMA]
        self.assertTrue(
            can_run_model(GEMMA, free_mib=required + BUFFER, ollama_loaded_mib=0,
                          model_vram_mib=TEST_VRAM, safety_buffer_mib=BUFFER)
        )

    def test_one_below_threshold(self) -> None:
        required = TEST_VRAM[GEMMA]
        self.assertFalse(
            can_run_model(GEMMA, free_mib=required + BUFFER - 1, ollama_loaded_mib=0,
                          model_vram_mib=TEST_VRAM, safety_buffer_mib=BUFFER)
        )

    def test_none_free_vram_always_true(self) -> None:
        self.assertTrue(
            can_run_model(GEMMA, free_mib=None, ollama_loaded_mib=0,
                          model_vram_mib=TEST_VRAM, safety_buffer_mib=BUFFER)
        )

    def test_unknown_model_always_true(self) -> None:
        # Model not in dict → optimistic, allow
        self.assertTrue(
            can_run_model("unknown-model:latest", free_mib=100, ollama_loaded_mib=0,
                          model_vram_mib=TEST_VRAM, safety_buffer_mib=BUFFER)
        )

    def test_lighter_model_fits_when_heavy_does_not(self) -> None:
        # 8 000 free, no ollama loaded; gemma (18 000 req) doesn't fit, qwen (6 000 req) does
        self.assertFalse(
            can_run_model(GEMMA, free_mib=8_000, ollama_loaded_mib=0,
                          model_vram_mib=TEST_VRAM, safety_buffer_mib=BUFFER)
        )
        self.assertTrue(
            can_run_model(QWEN, free_mib=8_000, ollama_loaded_mib=0,
                          model_vram_mib=TEST_VRAM, safety_buffer_mib=BUFFER)
        )


# ---------------------------------------------------------------------------
# select_next_batch
# ---------------------------------------------------------------------------


class TestSelectNextBatch(unittest.TestCase):

    def _sel(self, pending, free_mib, ollama_mib=0):
        return select_next_batch(
            pending, free_mib, ollama_mib,
            model_vram_mib=TEST_VRAM,
            safety_buffer_mib=BUFFER,
        )

    def test_empty_pending_returns_none(self) -> None:
        self.assertIsNone(self._sel([], free_mib=20_000))

    def test_unknown_vram_returns_first_pending(self) -> None:
        batches = [_sub(QWEN, "qwen-1"), _sub(GEMMA, "gemma-1")]
        result = self._sel(batches, free_mib=None)
        self.assertIs(result, batches[0])

    def test_prefers_heaviest_fitting_model(self) -> None:
        # Both models fit → should pick gemma4:26b (heavier)
        batches = [_sub(QWEN, "qwen-first"), _sub(GEMMA, "gemma-second")]
        result = self._sel(batches, free_mib=25_000)
        self.assertEqual(result, _sub(GEMMA, "gemma-second"))

    def test_prefers_heaviest_even_when_listed_last(self) -> None:
        batches = [_sub(QWEN, "qwen-a"), _sub(GEMMA, "gemma-b"), _sub(QWEN, "qwen-c")]
        result = self._sel(batches, free_mib=25_000)
        self.assertEqual(result.model, GEMMA)

    def test_falls_back_to_lighter_model_when_heavy_does_not_fit(self) -> None:
        # 8 000 free: gemma (needs 19 000) doesn't fit, qwen (needs 7 000) does
        batches = [_sub(GEMMA, "gemma-x"), _sub(QWEN, "qwen-y")]
        result = self._sel(batches, free_mib=8_000)
        self.assertEqual(result.model, QWEN)

    def test_returns_none_when_nothing_fits(self) -> None:
        # 3 000 free: neither model fits
        batches = [_sub(GEMMA, "g"), _sub(QWEN, "q")]
        result = self._sel(batches, free_mib=3_000)
        self.assertIsNone(result)

    def test_ollama_loaded_vram_enables_gemma_batch(self) -> None:
        # free=5 000, ollama_loaded=18 000 → effective=23 000 ≥ 19 000
        batches = [_sub(GEMMA, "gemma-next")]
        result = self._sel(batches, free_mib=5_000, ollama_mib=18_000)
        self.assertIs(result, batches[0])

    def test_ollama_loaded_does_not_help_when_still_insufficient(self) -> None:
        # free=500, ollama_loaded=6 000 → effective=6 500 < 19 000
        batches = [_sub(GEMMA, "gemma-no")]
        result = self._sel(batches, free_mib=500, ollama_mib=6_000)
        self.assertIsNone(result)

    def test_multiple_pending_gemma_picks_first(self) -> None:
        batches = [
            _sub(GEMMA, "g1"), _sub(QWEN, "q1"),
            _sub(GEMMA, "g2"), _sub(QWEN, "q2"),
        ]
        result = self._sel(batches, free_mib=25_000)
        self.assertEqual(result.name, "g1")

    def test_only_qwen_pending_when_vram_tight(self) -> None:
        batches = [_sub(QWEN, "q1"), _sub(QWEN, "q2")]
        result = self._sel(batches, free_mib=10_000)
        self.assertEqual(result.name, "q1")

    def test_heavy_model_pending_but_nothing_else_and_fits(self) -> None:
        batches = [_sub(GEMMA, "g")]
        result = self._sel(batches, free_mib=25_000)
        self.assertIs(result, batches[0])

    def test_unknown_model_selected_when_others_dont_fit(self) -> None:
        # An unknown model should be selected even when known models don't fit
        unknown = SubBatch(path=Path("/x"), name="unknown-batch", model="newmodel:7b")
        batches = [_sub(GEMMA, "g"), unknown]
        result = self._sel(batches, free_mib=500)
        self.assertEqual(result.name, "unknown-batch")

    def test_skip_reason_batches_are_not_in_pending(self) -> None:
        # Skipped batches should never be passed into pending; verify select
        # ignores them if caller accidentally includes them — but by convention
        # callers filter them out. This test just documents the expectation.
        skipped = SubBatch(path=Path("/x"), name="skip-me",
                           model=GEMMA, skip_reason="already done")
        batches = [skipped]
        # With enough VRAM, it would be returned (scheduler doesn't know about skip)
        result = self._sel(batches, free_mib=25_000)
        self.assertEqual(result, skipped)  # scheduler is skip-unaware; caller filters


# ---------------------------------------------------------------------------
# DEFAULT_MODEL_VRAM_MIB constants sanity checks
# ---------------------------------------------------------------------------


class TestDefaultConstants(unittest.TestCase):

    def test_gemma_larger_than_qwen(self) -> None:
        self.assertGreater(
            DEFAULT_MODEL_VRAM_MIB[GEMMA],
            DEFAULT_MODEL_VRAM_MIB[QWEN],
        )

    def test_buffer_is_positive(self) -> None:
        self.assertGreater(VRAM_SAFETY_BUFFER_MIB, 0)

    def test_select_uses_default_constants_correctly(self) -> None:
        """select_next_batch with real DEFAULT_MODEL_VRAM_MIB behaves as expected."""
        batches = [_sub(GEMMA, "g"), _sub(QWEN, "q")]
        # With 24 GB (24 576 MiB) free (RTX 4090), gemma should win
        result = select_next_batch(batches, free_mib=24_576, ollama_loaded_mib=0,
                                   model_vram_mib=DEFAULT_MODEL_VRAM_MIB)
        self.assertEqual(result.model, GEMMA)

    def test_select_prefers_qwen_on_constrained_gpu(self) -> None:
        """When ~15 GB is free, gemma4-26b-ctx32k (~20 GB needed) doesn't fit but qwen does."""
        batches = [_sub(GEMMA, "g"), _sub(QWEN, "q")]
        result = select_next_batch(batches, free_mib=15_000, ollama_loaded_mib=0,
                                   model_vram_mib=DEFAULT_MODEL_VRAM_MIB)
        self.assertEqual(result.model, QWEN)

    def test_nothing_fits_on_tiny_gpu(self) -> None:
        batches = [_sub(GEMMA, "g"), _sub(QWEN, "q")]
        result = select_next_batch(batches, free_mib=1_000, ollama_loaded_mib=0,
                                   model_vram_mib=DEFAULT_MODEL_VRAM_MIB)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
