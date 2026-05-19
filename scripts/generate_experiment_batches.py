#!/usr/bin/env python3
"""
Generate experiment batch YAMLs from the BugsInPy sampling strategy
defined in docs/experiment-plan.md.

Sampling rules:
  - Excluded:  pandas, cookiecutter (infra broken) +
               fastapi, httpie, youtube-dl, keras, matplotlib, sanic, spacy
               (confirmed infra-incompatible after trace analysis, 2026-05-19).
  - Included (cap=5 each): 8 remaining projects.
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

# Infra-incompatible after architecture-check and trace analysis (2026-05-19).
EXCLUDED = {
    "pandas", "cookiecutter",
    "fastapi", "httpie", "youtube-dl", "keras", "matplotlib", "sanic", "spacy",
}

# 8 projects with confirmed infra from architecture-check smoke runs.
INCLUDED = {
    "thefuck", "PySnooper", "tornado", "black", "tqdm", "scrapy", "luigi", "ansible",
}

# Uniform cap per project: 5 bugs × 8 projects = 40 bugs total.
# 5 slots: one per difficulty tier (bajo/medio/alto) + one extra bajo + one confirmed/priority.
CAP = 5
CAPS: dict[str, int] = {p: CAP for p in INCLUDED}

# Confirmed working (test passed) in previous experiments; prioritised within difficulty tier.
# Updated after architecture-check batch (2026-05-17/19): pysnooper-1 and tqdm-1 succeeded.
CONFIRMED: dict[str, set[int]] = {
    "thefuck":   {1, 2, 5, 6, 7},
    "tornado":   {9},
    "PySnooper": {1},
    "tqdm":      {1},
}

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
    confirmed: set[int],
) -> list[int]:
    """
    Pick up to `cap` bug IDs with four-phase logic:
      1. One bug per difficulty level (confirmed preferred; unconfirmed shuffled)
      1b. A second bajo bug (extra easy slot)
      2. Fill remaining slots with confirmed bugs not yet chosen
      3. Fill remaining with lowest-difficulty bugs (shuffled within tier)
    """
    by_level: dict[str, list[dict]] = {"bajo": [], "medio": [], "alto": []}
    for b in bugs:
        by_level[b["difficulty"]].append(b)
    # Within each tier: confirmed first (deterministic), unconfirmed randomised.
    for lvl in by_level:
        conf = [b for b in by_level[lvl] if b["confirmed"]]
        unconf = [b for b in by_level[lvl] if not b["confirmed"]]
        random.shuffle(unconf)
        by_level[lvl] = conf + unconf

    chosen: set[int] = set()

    # Phase 1: one from each difficulty tier
    for lvl in ("bajo", "medio", "alto"):
        if len(chosen) >= cap:
            break
        for b in by_level[lvl]:
            if b["id"] not in chosen:
                chosen.add(b["id"])
                break

    # Phase 1b: a second bajo bug (the extra easy slot)
    for b in by_level["bajo"]:
        if len(chosen) >= cap:
            break
        if b["id"] not in chosen:
            chosen.add(b["id"])
            break

    # Phase 2: remaining confirmed bugs
    for b in sorted((b for b in bugs if b["confirmed"] and b["id"] not in chosen), key=lambda b: b["id"]):
        if len(chosen) >= cap:
            break
        chosen.add(b["id"])

    # Phase 3: fill remaining slots, preferring bajo → medio → alto (already shuffled)
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
        confirmed = CONFIRMED.get(project, set())
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
                    "confirmed": bug_id in confirmed,
                }
            )

        selection[project] = _pick_stratified(bug_data, cap, confirmed)

    return selection


# ── YAML generation ───────────────────────────────────────────────────────────

ARCHITECTURES = [
    "mono_agent",
    "multi_agent_orchestrator",
    "planner_executor",
]

# Uniform run parameters — identical across all architectures for fair comparison.
MAX_TURNS = 20
MAX_ITERATIONS = 3
TIMEOUT_SECONDS = 900
ITERATION_TIMEOUT_SECONDS = 500

# (provider, model, label_for_filename, sequential, extra_body)
# sequential=True  → local GPU, must run one batch at a time
# sequential=False → API call, can overlap with Ollama or other API batches
# extra_body       → passed as llm.extra_body; used for model-specific params (e.g. Qwen think mode)
MODELS = [
    ("ollama", "qwen3.6:35b",   "qwen3.6-35b",   True,  {"think": False}),
    ("ollama", "gemma4:27b",    "gemma4-27b",    True,  None),
    ("openai", "gpt-5.4-mini",  "gpt-5.4-mini",  False, None),
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
) -> str:
    llm_cfg: dict = {
        "provider": provider,
        "model": model,
        "max_turns": MAX_TURNS,
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

    ollama_models = [(p, m, l, s, _) for p, m, l, s, _ in MODELS if s]
    api_models    = [(p, m, l, s, _) for p, m, l, s, _ in MODELS if not s]
    combos = len(ARCHITECTURES) * len(MODELS)
    print(f"\n{'='*60}")
    print(f"Generating {combos} batch files ({len(ARCHITECTURES)} arch × {len(MODELS)} models)")
    print(f"  Ollama (sequential): {[m for _, m, _, _, _ in ollama_models]}")
    print(f"  API    (parallel OK): {[m for _, m, _, _, _ in api_models]}")
    print(f"  Uniform params: max_turns={MAX_TURNS}, max_iterations={MAX_ITERATIONS}, "
          f"timeout={TIMEOUT_SECONDS}s, iter_timeout={ITERATION_TIMEOUT_SECONDS}s")
    print(f"Output dir: {out_dir}")
    print(f"{'='*60}\n")

    for arch in ARCHITECTURES:
        for provider, model, model_label, _sequential, extra_body in MODELS:
            arch_label = arch.replace("_", "-")
            filename = f"bugsinpy-{arch_label}-{model_label}.yaml"
            name = f"experiment-bugsinpy-{arch_label}-{model_label}"
            description = (
                f"TFM experiment — BugsInPy subset ({total} bugs), "
                f"{arch}, {model}"
            )

            content = _batch_yaml(
                name=name,
                description=description,
                dataset_ref=DATASET_REF,
                architecture=arch,
                provider=provider,
                model=model,
                bug_ids=all_bug_ids,
                extra_body=extra_body,
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
            for provider, model, model_label, _sequential, extra_body in MODELS:
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
