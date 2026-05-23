#!/usr/bin/env python3
"""
Generate experiment batch YAMLs from the BugsInPy sampling strategy
defined in docs/experiment-plan.md.

Sampling rules:
  - Excluded: projects with confirmed system-level infra failures
    (missing compilers, CUDA drivers, broken test runners, etc.) that
    prevent any bug from being set up or tested regardless of the agent.
    Currently: pandas, cookiecutter, keras, matplotlib, sanic, spacy.
  - Included (cap=5 each): all remaining projects with working infra.
  - Within each project: stratified by difficulty (bajo/medio/alto),
    confirmed bugs from previous experiments prioritised.
    Selection within each tier is randomised to avoid systematic bias.

Usage:
    python scripts/generate_experiment_batches.py [--dry-run] [--out-dir DIR]
"""

from __future__ import annotations

import argparse
import random
import re
from pathlib import Path

import yaml

# ── Repo paths ────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
BUGSINPY_ROOT = Path("~/Projects/BugsInPy").expanduser()
DEFAULT_OUT = REPO_ROOT / "batches" / "experiment"
DATASET_REF = "../../datasets/bugsinpy-full.yaml"
QUIXBUGS_DATASET_REF = "../../datasets/quixbugs.yaml"

# ── Sampling config ───────────────────────────────────────────────────────────

# Projects excluded due to confirmed system-level infra failures:
#   pandas      — requires Cython compilation (gcc missing in Docker image, 15-20 min/env)
#   cookiecutter — uses tox with Python 2.7/3.3/3.4/pypy envs unavailable in container
#   keras        — requires CUDA drivers (libcuda.so.1 not present)
#   matplotlib   — requires compiled C extension (ft2font) with FreeType headers
#   sanic        — pytest_benchmark version conflict causes conftest to fail on load
#   spacy        — requires g++ for C++ extensions (cymem, murmurhash)
EXCLUDED = {
    "pandas", "cookiecutter", "keras", "matplotlib", "sanic", "spacy",
}

# All remaining projects with confirmed working infra (smoke-tests or prior experiment runs).
INCLUDED = {
    "thefuck", "PySnooper", "tornado", "black", "tqdm", "scrapy", "luigi", "ansible",
    "youtube-dl", "httpie", "fastapi",
}

# Uniform cap per project: 5 bugs × 11 projects = up to 55 bugs total.
# 5 slots: one per difficulty tier (bajo/medio/alto) + one extra bajo + one confirmed/priority.
CAP = 5
CAPS: dict[str, int] = {p: CAP for p in INCLUDED}



# ── Difficulty thresholds (relative to BugsInPy) ─────────────────────────────

# Under these rules, all BugsInPy bugs are already medium-high in absolute terms.
# This is a within-dataset gradation only.
#   bajo  : 1 source file, ≤5 lines changed
#   medio : 1 source file, 6-20 lines changed
#   alto  : 1 source file, >20 lines changed  OR  ≥2 source files

TEST_RE = re.compile(
    r"(^|/)(test|tests|doc|docs)/|_test\.py$|test_.*\.py$|\.rst$|\.md$|\.txt$|ChangeLog$"
)


def _difficulty(src_files: int, lines: int) -> str:
    if src_files >= 2 or lines > 20:
        return "alto"
    if lines >= 6:
        return "medio"
    return "bajo"


# ── Patch analysis ────────────────────────────────────────────────────────────


def _analyze_patch(patch_path: Path) -> tuple[int, int]:
    """Return (source_file_count, lines_changed) from a bug_patch.txt."""
    text = patch_path.read_text(errors="replace")
    source_files: set[str] = set()
    current_is_source = False
    lines = 0

    for line in text.splitlines():
        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/(.+) b/", line)
            if m:
                fpath = m.group(1)
                current_is_source = not TEST_RE.search(fpath)
                if current_is_source:
                    source_files.add(fpath)
        elif current_is_source and line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            lines += 1

    return len(source_files), lines


# ── Selection logic ───────────────────────────────────────────────────────────


def _pick_stratified(
    bugs: list[dict],
    cap: int,
) -> list[int]:
    """
    Pick up to `cap` bug IDs with stratified random sampling:
      1. One randomly chosen bug per difficulty tier (bajo, medio, alto)
      2. A second bajo bug (extra easy slot)
      3. Fill remaining slots randomly, preferring bajo → medio → alto
    Within each tier the order is shuffled to avoid systematic bias.
    """
    by_level: dict[str, list[dict]] = {"bajo": [], "medio": [], "alto": []}
    for b in bugs:
        by_level[b["difficulty"]].append(b)
    for lvl in by_level:
        random.shuffle(by_level[lvl])

    chosen: set[int] = set()

    # Phase 1: one from each difficulty tier
    for lvl in ("bajo", "medio", "alto"):
        if len(chosen) >= cap:
            break
        for b in by_level[lvl]:
            if b["id"] not in chosen:
                chosen.add(b["id"])
                break

    # Phase 2: a second bajo bug (extra easy slot)
    for b in by_level["bajo"]:
        if len(chosen) >= cap:
            break
        if b["id"] not in chosen:
            chosen.add(b["id"])
            break

    # Phase 3: fill remaining slots, preferring bajo → medio → alto
    for lvl in ("bajo", "medio", "alto"):
        for b in by_level[lvl]:
            if len(chosen) >= cap:
                break
            if b["id"] not in chosen:
                chosen.add(b["id"])
        if len(chosen) >= cap:
            break

    return sorted(chosen)


def select_bugs(bugsinpy_root: Path) -> dict[str, list[int]]:
    """
    Analyse all bug patches and return {project: [selected_bug_ids]}.
    """
    projects_dir = bugsinpy_root / "projects"
    selection: dict[str, list[int]] = {}

    for project_dir in sorted(projects_dir.iterdir()):
        project = project_dir.name
        if not project_dir.is_dir() or project in EXCLUDED:
            continue
        if project not in INCLUDED:
            continue

        bugs_dir = project_dir / "bugs"
        if not bugs_dir.exists():
            continue

        cap = CAPS[project]
        bug_data: list[dict] = []

        for bug_dir in sorted(bugs_dir.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else 9999):
            if not bug_dir.name.isdigit():
                continue
            bug_id = int(bug_dir.name)
            patch = bug_dir / "bug_patch.txt"
            if not patch.exists():
                continue
            src_files, lines = _analyze_patch(patch)
            bug_data.append(
                {
                    "id": bug_id,
                    "src_files": src_files,
                    "lines": lines,
                    "difficulty": _difficulty(src_files, lines),
                }
            )

        selection[project] = _pick_stratified(bug_data, cap)

    return selection


# ── YAML generation ───────────────────────────────────────────────────────────

ARCHITECTURES = [
    "mono_agent",
    "multi_agent_orchestrator",
    "planner_executor",
]

# Uniform run parameters — identical across all architectures for fair comparison.
MAX_TURNS = 30
MAX_ITERATIONS = 3
TIMEOUT_SECONDS = 1500
ITERATION_TIMEOUT_SECONDS = 600

# (provider, model, label_for_filename, sequential, extra_body, max_turns)
# sequential=True  → local GPU, must run one batch at a time
# sequential=False → API call, can overlap with Ollama or other API batches
# extra_body       → passed as llm.extra_body; used for model-specific params (e.g. Qwen think mode)
# max_turns        → per-model override; API models use a lower cap to control token cost
#
# NOTE: num_ctx is baked into the Ollama Modelfile of each derived model — the /v1/
# endpoint ignores num_ctx passed in extra_body (Ollama uses the value at load time).
# Modelfiles: qwen3.5-9b-ctx65k (65 536) and gemma4-26b-ctx32k (32 768).
# VRAM measured on RTX 4090 (24 564 MiB):
#   qwen3.5-9b-ctx65k  → ~10 700 MiB  (weights 6 754 + KV@65K ~3 946 MiB Q4)
#   gemma4-26b-ctx32k  → 19 453 MiB   (weights ~18 771 + KV@32K ~682 MiB — GQA)
MODELS = [
    ("ollama", "qwen3.5-9b-ctx65k", "qwen3.5-9b",  True,  {"think": False}, MAX_TURNS),
    ("ollama", "gemma4-26b-ctx32k", "gemma4-26b",   True,  None,             MAX_TURNS),
    # gpt-5.4-mini: max_turns reduced to 15 to bound token cost (avg ~700K input tokens
    # per run with 30 turns; context grows linearly with turns).
    ("openai", "gpt-5.4-mini",      "gpt-5.4-mini", False, None,             15),
]

# ── QuixBugs stratified subset (20 bugs) ──────────────────────────────────────────
#
# Difficulty is determined by algorithmic complexity, not patch size.
# All QuixBugs bugs are single-file, single-function — patch size is uninformative.
#
# Simple (8): linear algorithms, trivial recursion, basic data structures
# Intermediate (6): graph traversal, stack-based parsing, structural recursion
# Advanced (6): dynamic programming, complex graph algorithms

QUIXBUGS_SELECTION: list[str] = [
    # Simple — 8 bugs
    "bitcount",               # bit manipulation, iterative
    "find_in_sorted",         # binary search
    "gcd",                    # Euclid’s algorithm
    "max_sublist_sum",        # Kadane’s algorithm
    "mergesort",              # divide-and-conquer sort
    "quicksort",              # partition-based sort
    "sieve",                  # Sieve of Eratosthenes
    "to_base",                # arithmetic base conversion
    # Intermediate — 6 bugs
    "breadth_first_search",   # BFS graph traversal
    "depth_first_search",     # DFS graph traversal
    "detect_cycle",           # cycle detection in directed graph
    "hanoi",                  # Tower of Hanoi (classic recursion)
    "is_valid_parenthesization",  # stack-based bracket validation
    "rpn_eval",               # reverse-Polish notation evaluator (stack)
    # Advanced — 6 bugs
    "knapsack",               # 0/1 knapsack (DP)
    "levenshtein",            # edit distance (DP)
    "lcs_length",             # longest common subsequence (DP)
    "minimum_spanning_tree",  # MST (Kruskal / Prim)
    "shortest_path_length",   # Dijkstra single-source
    "topological_ordering",   # topological sort (DFS-based)
]


def _batch_yaml(
    name: str,
    description: str,
    dataset_ref: str,
    architecture: str,
    provider: str,
    model: str,
    bug_ids: list[str],
    extra_body: dict | None = None,
    max_turns: int = MAX_TURNS,
) -> str:
    llm_cfg: dict = {
        "provider": provider,
        "model": model,
        "max_turns": max_turns,
    }
    if extra_body is not None:
        llm_cfg["extra_body"] = extra_body
    data: dict = {
        "name": name,
        "description": description,
        "dataset": dataset_ref,
        "global": {
            "architecture": architecture,
            "llm": llm_cfg,
            "max_iterations": MAX_ITERATIONS,
            "timeout_seconds": TIMEOUT_SECONDS,
            "iteration_timeout_seconds": ITERATION_TIMEOUT_SECONDS,
            "capture_errors": True,
        },
        "bugs": bug_ids,
    }
    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)


def generate(
    selection: dict[str, list[int]],
    out_dir: Path,
    dry_run: bool,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    all_bug_ids = [f"{project}-{bug_id}" for project, ids in sorted(selection.items()) for bug_id in ids]
    total = len(all_bug_ids)

    print(f"\n{'='*60}")
    print(f"BugsInPy selection: {total} bugs across {len(selection)} projects")
    print(f"{'='*60}")
    for project, ids in sorted(selection.items()):
        print(f"  {project:20s} (cap={CAPS[project]}): {ids}")

    ollama_models = [(p, m, l, s, eb, t) for p, m, l, s, eb, t in MODELS if s]
    api_models    = [(p, m, l, s, eb, t) for p, m, l, s, eb, t in MODELS if not s]
    combos = len(ARCHITECTURES) * len(MODELS) * len(selection)
    print(f"\n{'='*60}")
    print(f"Generating {combos} BugsInPy batch files ({len(ARCHITECTURES)} arch × {len(MODELS)} models × {len(selection)} repos)")
    print(f"  Ollama (sequential): {[m for _, m, _, _, _, _ in ollama_models]}")
    print(f"  API    (parallel OK): {[m for _, m, _, _, _, _ in api_models]}")
    model_turns = {l: t for _, _, l, _, _, t in MODELS}
    print(f"  max_turns per model: {model_turns}  |  max_iterations={MAX_ITERATIONS}, "
          f"timeout={TIMEOUT_SECONDS}s, iter_timeout={ITERATION_TIMEOUT_SECONDS}s")
    print(f"Output dir: {out_dir}")
    print(f"{'='*60}\n")

    for arch in ARCHITECTURES:
        for provider, model, model_label, _sequential, extra_body, max_turns in MODELS:
            arch_label = arch.replace("_", "-")
            for project, ids in sorted(selection.items()):
                project_bug_ids = [f"{project}-{bug_id}" for bug_id in ids]
                filename = f"bugsinpy-{arch_label}-{model_label}-{project}.yaml"
                name = f"experiment-bugsinpy-{arch_label}-{model_label}-{project}"
                description = (
                    f"TFM experiment — BugsInPy {project} ({len(ids)} bugs), "
                    f"{arch}, {model}"
                )

                content = _batch_yaml(
                    name=name,
                    description=description,
                    dataset_ref=DATASET_REF,
                    architecture=arch,
                    provider=provider,
                    model=model,
                    bug_ids=project_bug_ids,
                    extra_body=extra_body,
                    max_turns=max_turns,
                )

                path = out_dir / filename
                if dry_run:
                    print(f"[dry-run] Would write: {path.relative_to(REPO_ROOT)}")
                else:
                    path.write_text(content)
                    print(f"Written: {path.relative_to(REPO_ROOT)}")

    # QuixBugs batches (stratified subset of 20 bugs)
    quixbugs_dataset = REPO_ROOT / "datasets" / "quixbugs.yaml"
    if quixbugs_dataset.exists():
        qb_total = len(QUIXBUGS_SELECTION)
        print(f"\nQuixBugs selection: {qb_total} bugs (stratified: 8 simple, 6 intermediate, 6 advanced)")
        print(f"  {QUIXBUGS_SELECTION}")
        print()
        for arch in ARCHITECTURES:
            for provider, model, model_label, _sequential, extra_body, max_turns in MODELS:
                arch_label = arch.replace("_", "-")
                filename = f"quixbugs-{arch_label}-{model_label}.yaml"
                name = f"experiment-quixbugs-{arch_label}-{model_label}"
                description = (
                    f"TFM experiment — QuixBugs subset ({qb_total} bugs, stratified), {arch}, {model}"
                )
                content = _batch_yaml(
                    name=name,
                    description=description,
                    dataset_ref=QUIXBUGS_DATASET_REF,
                    architecture=arch,
                    provider=provider,
                    model=model,
                    bug_ids=QUIXBUGS_SELECTION,
                    extra_body=extra_body,
                    max_turns=max_turns,
                )
                path = out_dir / filename
                if dry_run:
                    print(f"[dry-run] Would write: {path.relative_to(REPO_ROOT)}")
                else:
                    path.write_text(content)
                    print(f"Written: {path.relative_to(REPO_ROOT)}")
    else:
        print(f"\n[skip] QuixBugs dataset not found at {quixbugs_dataset}")


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bugsinpy-path", type=Path, default=BUGSINPY_ROOT, help="Path to BugsInPy repo")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT, help="Output directory for batch YAMLs")
    parser.add_argument("--dry-run", action="store_true", help="Print selection and file list without writing")
    args = parser.parse_args()

    if not args.bugsinpy_path.exists():
        raise SystemExit(f"BugsInPy repo not found at {args.bugsinpy_path}")

    selection = select_bugs(args.bugsinpy_path)
    generate(selection, args.out_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
