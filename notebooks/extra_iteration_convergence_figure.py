"""Genera la figura de convergencia por iteracion para la memoria.

Lee el export canonico ``analysis_runs.csv`` y produce un grafico de barras
apiladas al 100 % que muestra la composicion semantica de los runs segun la
iteracion en la que terminaron, para cada benchmark. El mismo codigo se
mantiene como celda en ``final-experiment-analysis.ipynb``.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = REPO_ROOT / "notebooks" / "exports" / "final-experiment-analysis"
FIGURES_DIR = REPO_ROOT / "memoria" / "images"

VERDICT_ORDER = ["CORRECT", "PLAUSIBLE", "OVERFITTING", "FAIL"]
VERDICT_LABELS = {
    "CORRECT": "CORRECT",
    "PLAUSIBLE": "PLAUSIBLE",
    "OVERFITTING": "OVERFITTING",
    "FAIL": "FAIL",
}
VERDICT_COLORS = {
    "CORRECT": "#2CA02C",
    "PLAUSIBLE": "#1F77B4",
    "OVERFITTING": "#FF7F0E",
    "FAIL": "#8C8C8C",
}

sns.set_theme(style="whitegrid", context="notebook", font_scale=1.05)
plt.rcParams.update({"axes.titleweight": "bold", "savefig.facecolor": "white"})


def composition_by_iteration(frame: pd.DataFrame) -> pd.DataFrame:
    table = pd.crosstab(frame["total_iterations"], frame["verdict_clean"])
    for verdict in VERDICT_ORDER:
        if verdict not in table:
            table[verdict] = 0
    table = table[VERDICT_ORDER]
    table = table.reindex([1, 2, 3], fill_value=0)
    return table


def main() -> None:
    runs = pd.read_csv(EXPORT_DIR / "analysis_runs.csv")
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 9.0), sharex=True)
    for ax, dataset in zip(axes, ["QuixBugs", "BugsInPy"]):
        table = composition_by_iteration(runs[runs["dataset_label"] == dataset])
        totals = table.sum(axis=1)
        shares = table.div(totals.replace(0, 1), axis=0) * 100
        bottom = pd.Series(0.0, index=shares.index)
        for verdict in VERDICT_ORDER:
            ax.bar(
                shares.index.astype(str),
                shares[verdict],
                bottom=bottom,
                color=VERDICT_COLORS[verdict],
                edgecolor="white",
                width=0.62,
                label=VERDICT_LABELS[verdict],
            )
            bottom += shares[verdict]
        for x, iteration in enumerate(shares.index):
            correct_pct = shares.loc[iteration, "CORRECT"]
            ax.text(x, correct_pct / 2, f"{correct_pct:.0f}%", ha="center",
                    va="center", color="white", fontsize=11, fontweight="bold")
            ax.text(x, 102, f"n={int(totals.loc[iteration])}", ha="center",
                    va="bottom", fontsize=10, color="#333333")
        ax.set_title(dataset)
        ax.set_ylabel("Composicion de runs (%)")
        ax.set_ylim(0, 112)
        ax.margins(x=0.08)
    axes[-1].set_xlabel("Iteracion en la que termina el run")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4,
               bbox_to_anchor=(0.5, -0.02), frameon=False)
    fig.suptitle("Composicion semantica segun la iteracion de terminacion",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    for fmt in ("pdf", "png"):
        fig.savefig(FIGURES_DIR / f"final_iteration_convergence.{fmt}", dpi=180,
                    bbox_inches="tight")
    plt.close(fig)
    print("saved final_iteration_convergence to", FIGURES_DIR)


if __name__ == "__main__":
    main()
