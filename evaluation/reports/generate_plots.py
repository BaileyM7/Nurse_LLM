"""
Presentation-ready table and plots, generated from CSVs already on disk.

Outputs (to evaluation/results/):
  - results_table.png       : rendered headline table with best/2nd-best markers
  - headline_plot.png       : primary plot — grouped bar chart, systems × fidelity
                              metrics, with the 90% target line
  - robustness_plot.png     : edge-case pass rate heatmap (system × category)
  - ablation_plot.png       : Δ-fidelity from removing each component

Run AFTER the metric scripts have written their CSVs.

Usage:
    python -m evaluation.reports.generate_plots
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

random.seed(42)
np.random.seed(42)


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


# --- 1. Headline results table (rendered as an image) -----------------------

def render_results_table(fidelity: list[dict], out_path: Path) -> None:
    if not fidelity:
        print(f"  skip {out_path.name}: no fidelity data")
        return

    # Compute best / second-best per metric
    def marks(vals: list[float], higher_is_better: bool):
        idx = np.argsort(vals)[::-1] if higher_is_better else np.argsort(vals)
        best, second = (idx[0], idx[1] if len(idx) > 1 else -1)
        return best, second

    systems = [r["system"] for r in fidelity]
    faith = [float(r["faithful_rate"]) for r in fidelity]
    breaks = [float(r["character_break_rate"]) for r in fidelity]
    halluc = [float(r["hallucination_rate"]) for r in fidelity]
    turns = [r["total_turns"] for r in fidelity]

    best_f, second_f = marks(faith, higher_is_better=True)
    best_b, second_b = marks(breaks, higher_is_better=False)
    best_h, second_h = marks(halluc, higher_is_better=False)

    col_headers = ["System", "Faithful ↑", "Char-break ↓", "Halluc. ↓", "Turns"]
    rows = []
    for i, sys in enumerate(systems):
        rows.append([
            sys,
            f"{faith[i]:.1%}",
            f"{breaks[i]:.1%}",
            f"{halluc[i]:.1%}",
            str(turns[i]),
        ])

    fig, ax = plt.subplots(figsize=(9, 2 + 0.5 * len(rows)))
    ax.axis("off")
    table = ax.table(cellText=rows, colLabels=col_headers,
                     loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1, 1.7)

    # Header styling
    for c in range(len(col_headers)):
        cell = table[(0, c)]
        cell.set_facecolor("#1f3b4d")
        cell.set_text_props(color="white", weight="bold")

    # Highlight best / second-best
    def shade(row, col, rank):
        cell = table[(row + 1, col)]
        if rank == "best":
            cell.set_facecolor("#c8e6c9")  # green
            cell.set_text_props(weight="bold")
        elif rank == "second":
            cell.set_facecolor("#fff59d")  # yellow

    for i in range(len(systems)):
        rank = "best" if i == best_f else ("second" if i == second_f else None)
        if rank: shade(i, 1, rank)
        rank = "best" if i == best_b else ("second" if i == second_b else None)
        if rank: shade(i, 2, rank)
        rank = "best" if i == best_h else ("second" if i == second_h else None)
        if rank: shade(i, 3, rank)

    ax.set_title(
        "Response Fidelity by System  (green = best, yellow = 2nd-best)",
        fontsize=14, weight="bold", pad=20,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out_path}")


# --- 2. Primary plot: grouped bar chart -------------------------------------

def render_headline_plot(fidelity: list[dict], out_path: Path) -> None:
    if not fidelity:
        print(f"  skip {out_path.name}: no fidelity data")
        return

    systems = [r["system"] for r in fidelity]
    faith = [float(r["faithful_rate"]) * 100 for r in fidelity]
    breaks = [float(r["character_break_rate"]) * 100 for r in fidelity]
    halluc = [float(r["hallucination_rate"]) * 100 for r in fidelity]

    x = np.arange(len(systems))
    width = 0.26

    fig, ax = plt.subplots(figsize=(10, 6))
    bar1 = ax.bar(x - width, faith, width, label="Faithful ↑", color="#2e7d32")
    bar2 = ax.bar(x,         breaks, width, label="Char-break ↓", color="#c62828")
    bar3 = ax.bar(x + width, halluc, width, label="Hallucination ↓", color="#ef6c00")

    # 90% target line
    ax.axhline(90, color="#1565c0", linestyle="--", linewidth=1.5,
               label="P2 target (90%)")

    # Value labels
    for bars in (bar1, bar2, bar3):
        for b in bars:
            h = b.get_height()
            ax.annotate(f"{h:.0f}%", xy=(b.get_x() + b.get_width() / 2, h),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=10)

    ax.set_ylabel("Rate (%)", fontsize=12)
    ax.set_xlabel("System", fontsize=12)
    ax.set_title("Fidelity Metrics by System (100 turns each)",
                 fontsize=14, weight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(systems, fontsize=11)
    ax.set_ylim(0, 105)
    ax.legend(loc="center right", framealpha=0.95)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out_path}")


# --- 3. Robustness heatmap --------------------------------------------------

def render_robustness_plot(edge: list[dict], out_path: Path) -> None:
    if not edge:
        print(f"  skip {out_path.name}: no edge-case data")
        return

    systems = sorted({r["system"] for r in edge})
    categories = sorted({r["category"] for r in edge})
    matrix = np.zeros((len(categories), len(systems)))
    for r in edge:
        i = categories.index(r["category"])
        j = systems.index(r["system"])
        matrix[i, j] = float(r["pass_rate"])

    fig, ax = plt.subplots(figsize=(8, 4.5))
    im = ax.imshow(matrix, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(systems)))
    ax.set_xticklabels(systems, fontsize=11)
    ax.set_yticks(range(len(categories)))
    ax.set_yticklabels(categories, fontsize=11)
    for i in range(len(categories)):
        for j in range(len(systems)):
            ax.text(j, i, f"{matrix[i, j]:.0%}",
                    ha="center", va="center",
                    color="black", fontsize=11, weight="bold")
    ax.set_title("Edge-Case Pass Rate by System",
                 fontsize=13, weight="bold", pad=12)
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Pass rate")
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out_path}")


# --- 4. Ablation plot -------------------------------------------------------

def render_ablation_plot(ablation: list[dict], out_path: Path) -> None:
    if not ablation:
        print(f"  skip {out_path.name}: no ablation data")
        return

    baseline = next((r for r in ablation if r["system"] == "baseline_full"), None)
    if not baseline:
        print(f"  skip {out_path.name}: no baseline_full row")
        return
    base_f = float(baseline["faithful_rate"])

    variants, deltas, absolutes = [], [], []
    for r in ablation:
        if r["system"] == "baseline_full":
            continue
        variants.append(r["system"])
        f = float(r["faithful_rate"])
        deltas.append((f - base_f) * 100)
        absolutes.append(f * 100)

    colors = ["#c62828" if d < 0 else "#2e7d32" for d in deltas]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(variants, deltas, color=colors, edgecolor="black")
    for b, abs_val in zip(bars, absolutes):
        h = b.get_height()
        label = f"{h:+.1f} pp\n({abs_val:.0f}%)"
        y = h + (0.5 if h >= 0 else -0.5)
        va = "bottom" if h >= 0 else "top"
        ax.annotate(label, xy=(b.get_x() + b.get_width() / 2, y),
                    ha="center", va=va, fontsize=10)

    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("Δ faithful rate vs baseline_full (pp)", fontsize=12)
    ax.set_xlabel("Ablation", fontsize=12)
    ax.set_title(f"Ablation Impact on Fidelity  (baseline_full = {base_f:.0%})",
                 fontsize=13, weight="bold")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="evaluation/results")
    args = parser.parse_args()
    rd = Path(args.results_dir)

    print("Generating presentation artifacts...")
    render_results_table(_read_csv(rd / "fidelity.csv"),
                         rd / "results_table.png")
    render_headline_plot(_read_csv(rd / "fidelity.csv"),
                         rd / "headline_plot.png")
    render_robustness_plot(_read_csv(rd / "edge_cases_summary.csv"),
                           rd / "robustness_plot.png")
    render_ablation_plot(_read_csv(rd / "ablation_fidelity.csv"),
                         rd / "ablation_plot.png")
    print(f"\nAll outputs in {rd}/")


if __name__ == "__main__":
    main()
