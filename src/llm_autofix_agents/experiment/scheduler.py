"""
GPU-aware experiment scheduler for Ollama models.

Core scheduling logic extracted here so it can be unit-tested
independently of the CLI and subprocess calls in run_experiment_ollama.py.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
import json

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Fallback VRAM estimates (MiB) when the Ollama API is unavailable.
# Values are measured on RTX 4090 (24 564 MiB total) and include weights + KV
# cache at the configured num_ctx (baked into each Modelfile-derived model).
# Safety buffer only needs to cover fragmentation — KV is already included.
DEFAULT_MODEL_VRAM_MIB: dict[str, int] = {
    "gemma4-26b-ctx32k": 19_453,  # measured: weights ~18 771 + KV@32K ~682 MiB (GQA)
    "qwen3.5-9b-ctx65k": 10_700,  # estimated: weights 6 754 + KV@65K ~3 946 MiB (Q4)
}

# Extra headroom above the total model VRAM (fragmentation only — KV already included).
VRAM_SAFETY_BUFFER_MIB: int = 512  # 0.5 GiB

OLLAMA_DEFAULT_HOST: str = "http://localhost:11500"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class SubBatch:
    path: Path
    name: str
    model: str          # e.g. "gemma4:26b"
    skip_reason: str | None = None


# ---------------------------------------------------------------------------
# GPU queries (I/O — mock these in tests)
# ---------------------------------------------------------------------------


def get_free_vram_mib() -> int | None:
    """Return free VRAM in MiB via nvidia-smi, or None if unavailable.

    Reports the minimum across all GPUs (worst-case available space).
    """
    try:
        r = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            return None
        values = [
            int(line.strip())
            for line in r.stdout.strip().splitlines()
            if line.strip().isdigit()
        ]
        return min(values) if values else None
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        return None


def get_ollama_loaded_vram_mib(host: str = OLLAMA_DEFAULT_HOST) -> int:
    """Return total VRAM (MiB) occupied by currently loaded Ollama models.

    Uses the ``size`` field from /api/ps, which equals the quantised model
    weight file size — a reliable approximation of actual VRAM usage.
    Returns 0 on any error so callers can safely proceed.
    """
    try:
        with urlopen(f"{host}/api/ps", timeout=5) as resp:
            data = json.loads(resp.read())
        total_bytes = sum(m.get("size", 0) for m in data.get("models", []))
        return total_bytes // (1024 * 1024)
    except (URLError, OSError, ValueError, KeyError):
        return 0


def get_ollama_model_sizes_mib(host: str = OLLAMA_DEFAULT_HOST) -> dict[str, int]:
    """Return {model_name: size_mib} for all models installed in Ollama.

    Model names are normalised: the ``:latest`` tag is stripped so that
    ``"gemma4-26b-ctx32k:latest"`` becomes ``"gemma4-26b-ctx32k"``, matching
    the names used in batch YAMLs and DEFAULT_MODEL_VRAM_MIB.
    Models with explicit non-default tags (e.g. ``gemma4:26b``) are unchanged.

    Falls back to an empty dict on error.
    """
    try:
        with urlopen(f"{host}/api/tags", timeout=5) as resp:
            data = json.loads(resp.read())
        return {
            m["name"].removesuffix(":latest"): m["size"] // (1024 * 1024)
            for m in data.get("models", [])
            if "name" in m and "size" in m
        }
    except (URLError, OSError, ValueError, KeyError):
        return {}


# ---------------------------------------------------------------------------
# Scheduling logic (pure — no I/O, fully testable)
# ---------------------------------------------------------------------------


def can_run_model(
    model: str,
    free_mib: int | None,
    ollama_loaded_mib: int,
    model_vram_mib: dict[str, int],
    safety_buffer_mib: int = VRAM_SAFETY_BUFFER_MIB,
) -> bool:
    """Return True if *model* can start given the current VRAM state.

    Logic
    -----
    ``effective_free = free_mib + ollama_loaded_mib``

    This accounts for the fact that whatever Ollama currently has loaded will
    be released (or kept, if it is the same model) before the new batch starts.
    The new model requires ``model_vram_mib[model] + safety_buffer_mib`` MiB.

    When ``free_mib`` is None (nvidia-smi unavailable) the function returns
    True so the caller can proceed rather than block indefinitely.
    """
    if free_mib is None:
        return True
    required = model_vram_mib.get(model)
    if required is None:
        return True  # unknown model — assume it fits
    effective_free = free_mib + ollama_loaded_mib
    return effective_free >= required + safety_buffer_mib


def select_next_batch(
    pending: list[SubBatch],
    free_mib: int | None,
    ollama_loaded_mib: int,
    model_vram_mib: dict[str, int],
    safety_buffer_mib: int = VRAM_SAFETY_BUFFER_MIB,
) -> SubBatch | None:
    """Pick the next batch to run given current GPU state.

    Strategy
    --------
    1. If VRAM is unknown (``free_mib is None``): return the first pending
       batch unchanged — sequential fallback, no blocking.
    2. Otherwise try models from heaviest to lightest VRAM requirement.
       Return the first pending batch whose model fits in effective free VRAM.
    3. If nothing fits: return ``None`` — the caller should sleep and retry.

    The "heaviest first" priority ensures that large models (gemma4-26b-ctx32k) are
    dispatched whenever there is sufficient headroom, leaving lighter runs
    (qwen3.5-9b-ctx65k) for periods of high contention.
    """
    if not pending:
        return None

    if free_mib is None:
        return pending[0]

    # Sort known models by VRAM requirement descending (heaviest = priority 0)
    sorted_models = sorted(
        model_vram_mib.keys(),
        key=lambda m: -model_vram_mib[m],
    )

    for model_name in sorted_models:
        if can_run_model(
            model_name, free_mib, ollama_loaded_mib, model_vram_mib, safety_buffer_mib
        ):
            for batch in pending:
                if batch.model == model_name:
                    return batch

    # Also check models not in model_vram_mib (unknown → can_run returns True)
    unknown_models = {b.model for b in pending} - set(model_vram_mib)
    for batch in pending:
        if batch.model in unknown_models:
            return batch

    return None  # nothing fits
