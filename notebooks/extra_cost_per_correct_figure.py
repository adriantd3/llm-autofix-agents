"""Regenera la figura de tokens por parche CORRECT para la memoria.

Lee el export canonico ``analysis_runs.csv`` y produce un grafico de barras
horizontales con los dos benchmarks apilados en vertical (una fila por
benchmark) para que no queden comprimidos en horizontal. El mismo codigo se
mantiene como celda en ``final-experiment-analysis.ipynb``.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = REPO_ROOT / "notebooks" / "exports" / "final-experiment-analysis"
FIGURES_DIR = REPO_ROOT / "memoria" / "images"

ARCH_ORDER = ["mono_agent", "multi_agent_orchestrator", "planner_executor"]
ARCH_LABELS = {
    "mono_agent": "Mono-agent",
    "multi_agent_orchestrator": "Orchestrator",
    "planner_executor": "Planner-Executor",
}
ARCH_COLORS = {
    "mono_agent": "#4C78A8",
    "multi_agent_orchestrator": "#F58518",
    "planner_executor": "#54A24B",
}

sns.set_theme(style="whitegrid", context="notebook", font_scale=1.05)
plt.rcParams.update({"axes.titleweight": "bold", "savefig.facecolor": "white"})


def main() -> None:
    runs = pd.read_csv(EXPORT_DIR / "analysis_runs.csv")
    label_to_arch = {v: k for k, v in ARCH_LABELS.items()}
    eff = (
        runs.groupby(["dataset_label", "model_label", "arch_label"], observed=True)
        .agg(
            correct=("judge_correct", "sum"),
            total_tokens_m=("tokens_k", lambda s: s.sum() / 1000.0),
        )
        .reset_index()
    )
    eff["tokens_m_per_correct"] = eff.apply(
        lambda r: r["total_tokens_m"] / r["correct"] if r["correct"] else np.nan,
        axis=1,
    )
    eff["config"] = eff["model_label"] + " / " + eff["arch_label"]

    fig, axes = plt.subplots(2, 1, figsize=(11, 12), sharex=False)
    for ax, dataset in zip(axes, ["QuixBugs", "BugsInPy"]):
        data = eff[eff["dataset_label"].eq(dataset)].sort_values(
            "tokens_m_per_correct", ascending=False
        )
        colors = [
            ARCH_COLORS.get(label_to_arch.get(str(a), ""), "#777777")
            for a in data["arch_label"]
        ]
        bars = ax.barh(data["config"], data["tokens_m_per_correct"],
                       color=colors, edgecolor="white")
        span = max(data["tokens_m_per_correct"].max() * 0.02, 0.03)
        for bar, value in zip(bars, data["tokens_m_per_correct"]):
            ax.text(value + span, bar.get_y() + bar.get_height() / 2,
                    f"{value:.2f}", va="center", fontsize=9)
        ax.set_title(f"Tokens por CORRECT - {dataset}")
        ax.set_xlabel("Millones de tokens por CORRECT")
        ax.set_ylabel("")
        sns.despine(ax=ax)
    handles = [plt.Rectangle((0, 0), 1, 1, color=ARCH_COLORS[a]) for a in ARCH_ORDER]
    labels = [ARCH_LABELS[a] for a in ARCH_ORDER]
    fig.legend(handles, labels, title="Arquitectura", ncol=3, loc="upper center",
               bbox_to_anchor=(0.5, 1.01), frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.97))

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    for fmt in ("pdf", "png"):
        fig.savefig(FIGURES_DIR / f"final_cost_per_correct.{fmt}", dpi=180,
                    bbox_inches="tight")
    plt.close(fig)
    bugsinpy = eff[eff.dataset_label.eq("BugsInPy")].sort_values("tokens_m_per_correct")
    print(bugsinpy[["config", "tokens_m_per_correct"]].round(2).to_string(index=False))
    print("saved final_cost_per_correct to", FIGURES_DIR)


if __name__ == "__main__":
    main()
