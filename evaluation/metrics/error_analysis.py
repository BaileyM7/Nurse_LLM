"""
Error analysis — reads the per-turn fidelity details produced by
metrics/fidelity.py and produces:

  (a) failure rate per scenario (which cases trip the patient up?)
  (b) most common hallucinated symptoms (confusion patterns)
  (c) character-break frequency per system
  (d) 5 qualitative failure examples per system (verbatim) for the report

Usage:
    python -m evaluation.metrics.error_analysis \\
        evaluation/results/fidelity_details.jsonl
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def load_details(path: str) -> list[dict]:
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def analyze(records: list[dict]) -> dict:
    # Per-system, per-scenario failure rate
    by_sys_scen: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in records:
        by_sys_scen[(r["system"], r["scenario_id"])].append(r)

    scenario_failure_rates: dict[str, list[tuple[str, float, int]]] = defaultdict(list)
    for (sys, scen), turns in by_sys_scen.items():
        n = len(turns)
        failed = sum(1 for t in turns if not t["faithful"])
        scenario_failure_rates[sys].append((scen, failed / n if n else 0, n))

    # Sort by failure rate descending per system
    for sys in scenario_failure_rates:
        scenario_failure_rates[sys].sort(key=lambda x: -x[1])

    # Most-common hallucinated terms per system
    hallucinated_terms: dict[str, Counter] = defaultdict(Counter)
    # Most-common break patterns per system
    break_patterns: dict[str, Counter] = defaultdict(Counter)
    # Qualitative failure examples per system (up to 5)
    examples: dict[str, list[dict]] = defaultdict(list)

    for r in records:
        for term in r.get("hallucinated_symptoms", []):
            hallucinated_terms[r["system"]][term] += 1
        for b in r.get("character_break_evidence", []):
            break_patterns[r["system"]][b] += 1
        if not r["faithful"] and len(examples[r["system"]]) < 5:
            examples[r["system"]].append({
                "scenario_id": r["scenario_id"],
                "student": r["student"],
                "patient": r["patient"],
                "hallucinated_symptoms": r.get("hallucinated_symptoms", []),
                "character_break_evidence": r.get("character_break_evidence", []),
            })

    return {
        "scenario_failure_rates": scenario_failure_rates,
        "hallucinated_terms": {k: v.most_common(10) for k, v in hallucinated_terms.items()},
        "break_patterns": {k: v.most_common(10) for k, v in break_patterns.items()},
        "examples": examples,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("details",
                        help="Path to fidelity_details.jsonl")
    parser.add_argument("--out-dir", default="evaluation/results")
    parser.add_argument("--top-n", type=int, default=5,
                        help="How many worst scenarios to list per system")
    args = parser.parse_args()

    records = load_details(args.details)
    if not records:
        raise SystemExit(f"No records in {args.details}")

    result = analyze(records)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Print worst scenarios per system
    print("\n=== Worst scenarios (highest failure rate) ===")
    for sys, rows in result["scenario_failure_rates"].items():
        print(f"\n[{sys}]")
        for scen, rate, n in rows[: args.top_n]:
            print(f"  {scen}: {rate:.1%}  ({n} turns)")

    # Hallucination frequencies
    print("\n=== Most common hallucinated symptom terms ===")
    for sys, terms in result["hallucinated_terms"].items():
        if not terms:
            continue
        print(f"\n[{sys}]")
        for term, count in terms:
            print(f"  {term}: {count}")

    print("\n=== Most common character-break phrases ===")
    for sys, patterns in result["break_patterns"].items():
        if not patterns:
            continue
        print(f"\n[{sys}]")
        for phrase, count in patterns:
            print(f"  {phrase!r}: {count}")

    # Save all outputs
    with open(out / "error_scenario_failure_rates.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["system", "scenario_id", "failure_rate", "turns"])
        for sys, rows in result["scenario_failure_rates"].items():
            for scen, rate, n in rows:
                w.writerow([sys, scen, round(rate, 3), n])

    with open(out / "error_hallucinated_terms.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["system", "term", "count"])
        for sys, terms in result["hallucinated_terms"].items():
            for t, c in terms:
                w.writerow([sys, t, c])

    with open(out / "error_examples.jsonl", "w") as f:
        for sys, exs in result["examples"].items():
            for e in exs:
                f.write(json.dumps({"system": sys, **e}) + "\n")

    print(f"\nArtifacts saved to {out}/")


if __name__ == "__main__":
    main()
