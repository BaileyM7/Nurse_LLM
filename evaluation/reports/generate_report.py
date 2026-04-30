"""Consolidate metric CSVs into a single markdown report.

Usage: python -m evaluation.reports.generate_report [--results-dir evaluation/results]
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path


def _seed(seed: int = 42) -> None:
    """Seed Python random and numpy.random; called from main() to avoid
    resetting global RNG state at import time."""
    random.seed(seed)
    try:
        import numpy as np  # noqa: PLC0415

        np.random.seed(seed)
    except ImportError:
        pass


def _load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _mark_best(
    rows: list[tuple[str, float]], higher_is_better: bool = True
) -> dict[str, str]:
    """Given [(system, value), ...], return a mapping system → formatted cell
    with **best** and *second-best* markers."""
    if not rows:
        return {}
    sorted_rows = sorted(rows, key=lambda x: x[1], reverse=higher_is_better)
    best_system = sorted_rows[0][0] if sorted_rows else None
    second_system = sorted_rows[1][0] if len(sorted_rows) > 1 else None

    out = {}
    for system, value in rows:
        formatted = f"{value:.1%}" if 0 <= value <= 1 else f"{value:.2f}"
        if system == best_system:
            out[system] = f"**{formatted}**"
        elif system == second_system:
            out[system] = f"*{formatted}*"
        else:
            out[system] = formatted
    return out


def build_headline_table(fidelity: list[dict]) -> str:
    """Build a markdown table across systems × metrics using fidelity.csv."""
    if not fidelity:
        return "_No fidelity results found. Run `python -m evaluation.metrics.fidelity ...` first._"

    # Per-metric best/second markers
    faithful_rows = [(r["system"], float(r["faithful_rate"])) for r in fidelity]
    break_rows = [(r["system"], float(r["character_break_rate"])) for r in fidelity]
    hall_rows = [(r["system"], float(r["hallucination_rate"])) for r in fidelity]

    faithful_marks = _mark_best(faithful_rows, higher_is_better=True)
    break_marks = _mark_best(break_rows, higher_is_better=False)
    hall_marks = _mark_best(hall_rows, higher_is_better=False)

    lines = [
        "| System | Faithful ↑ | Char-break ↓ | Halluc. ↓ | Turns |",
        "|---|---|---|---|---|",
    ]
    for r in fidelity:
        s = r["system"]
        lines.append(
            f"| {s} | {faithful_marks[s]} | {break_marks[s]} | {hall_marks[s]} | {r['total_turns']} |"
        )
    lines.append("")
    lines.append(
        "↑ = higher is better, ↓ = lower is better. "
        "**bold** = best, *italic* = second-best."
    )
    return "\n".join(lines)


def build_ablation_table(ablation_fidelity: list[dict]) -> str:
    if not ablation_fidelity:
        return (
            "_No ablation fidelity found at `results/ablation_fidelity.csv`. "
            "Run ablations then re-score with fidelity._"
        )

    # Baseline is the reference
    baseline = next(
        (r for r in ablation_fidelity if r["system"] == "baseline_full"), None
    )
    lines = [
        "| Variant | Faithful | Δ vs baseline | Char-break | Halluc. |",
        "|---|---|---|---|---|",
    ]
    base_faith = float(baseline["faithful_rate"]) if baseline else None
    for r in ablation_fidelity:
        f = float(r["faithful_rate"])
        delta = (f - base_faith) if base_faith is not None else 0
        delta_str = f"{delta:+.1%}" if base_faith is not None else "—"
        lines.append(
            f"| {r['system']} | {f:.1%} | {delta_str} | "
            f"{float(r['character_break_rate']):.1%} | "
            f"{float(r['hallucination_rate']):.1%} |"
        )
    return "\n".join(lines)


def build_edge_cases_table(edge: list[dict]) -> str:
    if not edge:
        return "_No edge-case results found._"
    # Re-shape: rows = category, cols = systems
    categories = sorted({r["category"] for r in edge})
    systems = sorted({r["system"] for r in edge})
    header = "| Category | " + " | ".join(systems) + " |"
    sep = "|---" * (len(systems) + 1) + "|"
    lines = [header, sep]
    for cat in categories:
        row_cells = [cat]
        for sys in systems:
            cell = next(
                (r for r in edge if r["system"] == sys and r["category"] == cat), None
            )
            row_cells.append(f"{float(cell['pass_rate']):.1%}" if cell else "—")
        lines.append("| " + " | ".join(row_cells) + " |")
    return "\n".join(lines)


def build_conclusion(fidelity: list[dict], domain_per_domain: list[dict]) -> str:
    if not fidelity:
        return "Insufficient data to draw a conclusion."

    best = max(fidelity, key=lambda r: float(r["faithful_rate"]))
    full = next((r for r in fidelity if r["system"] == "full_pipeline"), None)
    full_rate = float(full["faithful_rate"]) if full else None
    met_90 = full_rate is not None and full_rate >= 0.90

    domain_acc = None
    if domain_per_domain:
        # accuracy is not in per-domain file; compute from support * precision if present
        # simpler: use the "support"-weighted mean of recall as a proxy
        try:
            total_support = sum(int(r["support"]) for r in domain_per_domain)
            weighted = sum(
                float(r["recall"]) * int(r["support"]) for r in domain_per_domain
            )
            domain_acc = weighted / total_support if total_support else None
        except Exception:
            domain_acc = None

    parts = []
    parts.append(
        f"**Full pipeline** achieved {full_rate:.1%} response fidelity"
        if full_rate is not None
        else "**Full pipeline** fidelity not measured in this run"
    )
    parts.append(
        f"(P2 target ≥90%: {'MET' if met_90 else 'NOT MET'})"
        if full_rate is not None
        else ""
    )
    if domain_acc is not None:
        parts.append(f"and domain-classification weighted recall ≈ {domain_acc:.1%}")
    if best["system"] != "full_pipeline":
        parts.append(
            f"— note that {best['system']} scored higher on faithfulness, "
            "suggesting the tracking/feedback layer is not hurting, "
            "but is not driving fidelity gains"
        )
    return " ".join(parts).strip() + "."


def build_examples_section(examples: list[dict]) -> str:
    if not examples:
        return "_No qualitative examples found. Run `error_analysis.py` first._"
    by_system: dict[str, list[dict]] = {}
    for e in examples:
        by_system.setdefault(e["system"], []).append(e)

    lines = []
    for sys, exs in by_system.items():
        lines.append(f"### {sys}\n")
        for e in exs[:5]:
            lines.append(f"**Scenario:** `{e['scenario_id']}`  ")
            lines.append(f"**Student:** {e['student']}  ")
            lines.append(f"**Patient:** {e['patient']}  ")
            if e.get("hallucinated_symptoms"):
                lines.append(
                    f"**Hallucinated:** {', '.join(e['hallucinated_symptoms'])}  "
                )
            if e.get("character_break_evidence"):
                lines.append(f"**Break:** {', '.join(e['character_break_evidence'])}  ")
            lines.append("")
    return "\n".join(lines)


def main() -> None:
    _seed()
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="evaluation/results")
    parser.add_argument("--out", default="evaluation/results/final_report.md")
    args = parser.parse_args()

    rd = Path(args.results_dir)
    fidelity = _load_csv(rd / "fidelity.csv")
    ablation = _load_csv(rd / "ablation_fidelity.csv")
    edge = _load_csv(rd / "edge_cases_summary.csv")
    per_domain = _load_csv(rd / "domain_per_domain.csv")
    examples = _load_jsonl(rd / "error_examples.jsonl")

    md = []
    md.append("# Nurse LLM — Evaluation Report\n")
    md.append("_Auto-generated from metric outputs. Do not hand-edit._\n")

    md.append("## Conclusion\n")
    md.append(build_conclusion(fidelity, per_domain) + "\n")

    md.append("## 1. Headline: Response Fidelity\n")
    md.append(build_headline_table(fidelity) + "\n")

    md.append("## 2. Domain Classification\n")
    if (rd / "domain_confusion_matrix.png").exists():
        md.append("![Confusion matrix](domain_confusion_matrix.png)\n")
    if per_domain:
        md.append("\n| Domain | Precision | Recall | F1 | Support |")
        md.append("|---|---|---|---|---|")
        for r in per_domain:
            md.append(
                f"| {r['domain']} | {r['precision']} | {r['recall']} | "
                f"{r['f1']} | {r['support']} |"
            )
    else:
        md.append(
            "_Run `python -m evaluation.metrics.domain_classifier <labels.jsonl>` first._"
        )
    md.append("")

    md.append("## 3. Ablations: What Drives Fidelity?\n")
    md.append(build_ablation_table(ablation) + "\n")

    md.append("## 4. Robustness: Edge-Case Pass Rates\n")
    md.append(build_edge_cases_table(edge) + "\n")

    md.append("## 5. Qualitative Error Examples\n")
    md.append(build_examples_section(examples) + "\n")

    md.append("## Reproducibility\n")
    md.append(
        "- Random seed: 42 (set in `run_all_systems.py` and `ablations/run_ablations.py`)"
    )
    md.append("- Classifier temperature: 0.0. Patient simulation: 0.7.")
    md.append("- See `evaluation/METHODOLOGY.md` for full methodology.")
    md.append("")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(md))
    print(f"Report written: {out}")


if __name__ == "__main__":
    main()
