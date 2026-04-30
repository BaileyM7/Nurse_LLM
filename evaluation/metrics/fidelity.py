"""Response fidelity — checks each patient turn for hallucinated symptoms and character breaks.

Usage: python -m evaluation.metrics.fidelity <transcripts.jsonl> [--out results/fidelity.csv]
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

CHARACTER_BREAK_PATTERNS = [
    r"\bas an? ai\b",
    r"\bi(?:'m| am) (?:an? )?(?:language model|ai|artificial)",
    r"\bi cannot (?:provide|give) medical",
    r"\bplease (?:consult|see) (?:a|your) (?:doctor|physician|provider)\b",
    r"\byou (?:should|need to|must) (?:take|use) (?:aspirin|nitroglycerin|insulin|[a-z]+ ?mg)",
    r"\byour diagnosis is\b",
    r"\bi (?:diagnose|recommend you take)\b",
]

DIAGNOSTIC_LANGUAGE = [
    r"\bmyocardial infarction\b",
    r"\bheart attack is what\b",
    r"\bsepsis\b.*\byou have\b",
    r"\bappendicitis\b.*\byou have\b",
]

# Generic denial phrases — a patient saying "no I don't have that" is fine,
# not a hallucination even if they name a symptom.
DENIAL_PATTERNS = [
    r"\b(?:no|don't|do not|haven't|haven't been|not really|nope)\b",
    r"\bi (?:don't|haven't|haven[’']t|do not) (?:have|had|been|feel|notice)",
]

# Sentences / clauses describing ALLERGIC REACTIONS should not be scanned for
# "hallucinated symptoms" — the patient is describing what happens IF they
# take an allergen, not claiming a current symptom. Same for drug side effects.
ALLERGY_CONTEXT_PATTERNS = [
    r"\ballerg(?:ic|y|ies)\b",
    r"\breact(?:s|ed|ion|ions)?\b",
    r"\bcaus(?:e|es|ed|ing)\b",
    r"\bside[- ]effect",
    r"\bgives me\b",
    r"\bmakes me\b",
]


def _load_scenario(scenario_path: str) -> dict:
    with open(scenario_path) as f:
        return json.load(f)


def _symptom_tokens(scenario: dict) -> tuple[set[str], set[str]]:
    """Return (present_terms, absent_terms) — lowercased word sets for matching."""
    present = set()
    for name, detail in scenario.get("symptoms_present", {}).items():
        present.update(_tokenize(name))
        if isinstance(detail, dict):
            if detail.get("description"):
                present.update(_tokenize(detail["description"]))
            for field in ("character", "location", "radiation"):
                if detail.get(field):
                    present.update(_tokenize(detail[field]))
            for field in (
                "associated_symptoms",
                "aggravating_factors",
                "alleviating_factors",
            ):
                for item in detail.get(field, []):
                    present.update(_tokenize(item))

    absent = set()
    for name in scenario.get("symptoms_absent", []):
        absent.update(_tokenize(name))

    # Remove generic words that aren't symptom-specific
    stopwords = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "with",
        "in",
        "on",
        "at",
        "of",
        "to",
        "is",
        "it",
        "my",
        "i",
        "me",
        "you",
        "like",
        "felt",
        "feel",
        "been",
        "am",
        "pain",
        "feeling",
        "symptom",
        "symptoms",  # too generic
    }
    return present - stopwords, absent - stopwords


def _tokenize(s: str) -> set[str]:
    return set(re.findall(r"[a-z]+", (s or "").lower()))


def check_character_break(patient_text: str) -> list[str]:
    """Return list of character-break evidence phrases found."""
    hits = []
    text = patient_text.lower()
    for pat in CHARACTER_BREAK_PATTERNS + DIAGNOSTIC_LANGUAGE:
        m = re.search(pat, text)
        if m:
            hits.append(m.group(0))
    return hits


def _strip_allergy_context(text: str) -> str:
    """Strip parentheticals and allergy-reaction sentences to avoid false-positive hallucinations."""
    # Remove parenthetical content: "Penicillin (rash)" -> "Penicillin "
    stripped = re.sub(r"\([^)]*\)", "", text)
    kept = []
    for sentence in re.split(r"(?<=[.!?])\s+", stripped):
        s_lower = sentence.lower()
        if any(re.search(p, s_lower) for p in ALLERGY_CONTEXT_PATTERNS):
            continue
        kept.append(sentence)
    return " ".join(kept)


def check_hallucinated_symptoms(patient_text: str, scenario: dict) -> list[str]:
    """Return absent-symptom phrases the patient affirmatively claims (phrase match, not token)."""
    cleaned = _strip_allergy_context(patient_text)
    absent_phrases = [
        s.strip().lower()
        for s in scenario.get("symptoms_absent", [])
        if s and len(s.strip()) >= 3
    ]
    hits = []
    for sentence in re.split(r"(?<=[.!?])\s+", cleaned):
        s_lower = sentence.lower()
        if any(re.search(p, s_lower) for p in DENIAL_PATTERNS):
            continue
        for phrase in absent_phrases:
            if re.search(rf"\b{re.escape(phrase)}\b", s_lower):
                hits.append(phrase)
    return hits


def score_turn(patient_text: str, scenario: dict) -> dict:
    breaks = check_character_break(patient_text)
    halluc = check_hallucinated_symptoms(patient_text, scenario)
    faithful = len(breaks) == 0 and len(halluc) == 0
    return {
        "faithful": faithful,
        "character_break_evidence": breaks,
        "hallucinated_symptoms": halluc,
    }


def evaluate_transcripts(transcripts_path: str) -> dict:
    """Walk a JSONL of patient turns and compute fidelity per system."""
    # system → list of turn results
    by_system: dict[str, list[dict]] = defaultdict(list)
    scenario_cache: dict[str, dict] = {}

    with open(transcripts_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            sp = record["scenario_path"]
            if sp not in scenario_cache:
                scenario_cache[sp] = _load_scenario(sp)
            result = score_turn(record["patient"], scenario_cache[sp])
            result.update(
                {
                    "system": record["system"],
                    "scenario_id": record["scenario_id"],
                    "student": record["student"],
                    "patient": record["patient"],
                }
            )
            by_system[record["system"]].append(result)

    summary = {}
    for system, turns in by_system.items():
        n = len(turns)
        faithful = sum(1 for t in turns if t["faithful"])
        breaks = sum(1 for t in turns if t["character_break_evidence"])
        halluc = sum(1 for t in turns if t["hallucinated_symptoms"])
        summary[system] = {
            "total_turns": n,
            "faithful_rate": round(faithful / n, 3) if n else 0.0,
            "character_break_rate": round(breaks / n, 3) if n else 0.0,
            "hallucination_rate": round(halluc / n, 3) if n else 0.0,
            "target_met_90pct": (faithful / n >= 0.90) if n else False,
        }

    return {"summary": summary, "per_turn": by_system}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("transcripts", help="Path to transcripts JSONL")
    parser.add_argument("--out", default="evaluation/results/fidelity.csv")
    parser.add_argument(
        "--details-out", default="evaluation/results/fidelity_details.jsonl"
    )
    args = parser.parse_args()

    results = evaluate_transcripts(args.transcripts)

    print("\n=== Response Fidelity (P2 target: ≥90%) ===\n")
    for system, stats in results["summary"].items():
        status = "PASS" if stats["target_met_90pct"] else "FAIL"
        print(
            f"  {system:20s}  faithful={stats['faithful_rate']:.1%}  "
            f"breaks={stats['character_break_rate']:.1%}  "
            f"halluc={stats['hallucination_rate']:.1%}  [{status}]"
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    import csv

    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "system",
                "total_turns",
                "faithful_rate",
                "character_break_rate",
                "hallucination_rate",
                "target_met_90pct",
            ]
        )
        for system, stats in results["summary"].items():
            w.writerow(
                [
                    system,
                    stats["total_turns"],
                    stats["faithful_rate"],
                    stats["character_break_rate"],
                    stats["hallucination_rate"],
                    stats["target_met_90pct"],
                ]
            )
    print(f"\nSummary written to {out_path}")

    details_path = Path(args.details_out)
    with open(details_path, "w") as f:
        for _system, turns in results["per_turn"].items():
            for t in turns:
                f.write(json.dumps(t) + "\n")
    print(f"Per-turn details written to {details_path}")


if __name__ == "__main__":
    main()
