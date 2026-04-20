"""
Domain classification accuracy.

Takes a labeled JSONL file of student questions with gold domain labels, runs
each question through the same LLM prompt the full pipeline uses, then reports
accuracy, per-domain precision/recall/F1, and a confusion matrix.

Maps to P2 success criterion: "Assessment domain classification accuracy ≥85%".

Label file format (JSONL, one record per question):
    {"question": "Any chest pain?", "gold_domain": "HPI"}
    {"question": "Any allergies to medications?", "gold_domain": "Allergies"}

Valid gold labels: HPI, ROS, PMH, Medications, Allergies, Social_History,
Family_History, conversational.

Usage:
    python -m evaluation.metrics.domain_classifier <labels.jsonl>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # load OPENAI_API_KEY from .env before reading os.environ

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


DOMAINS = ["HPI", "ROS", "PMH", "Medications", "Allergies",
           "Social_History", "Family_History", "conversational"]


CLASSIFIER_PROMPT = """You classify nursing-assessment questions into one of these clinical domains:

- HPI: History of Present Illness (current symptoms, onset, character, severity, timing)
- ROS: Review of Systems (screening Qs about other body systems)
- PMH: Past Medical History (chronic conditions, prior diagnoses, surgeries)
- Medications: current meds
- Allergies: drug/food/environmental allergies
- Social_History: smoking, alcohol, drugs, occupation, living situation, exercise, diet
- Family_History: conditions in family members
- conversational: greetings, rapport-building, clarifications, not a clinical domain

Respond ONLY with the domain name, nothing else."""


def load_labels(path: str) -> list[dict]:
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _normalize(label: str) -> str:
    m = {
        "hpi": "HPI", "history_of_present_illness": "HPI",
        "ros": "ROS", "review_of_systems": "ROS",
        "pmh": "PMH", "past_medical_history": "PMH",
        "medications": "Medications", "meds": "Medications",
        "allergies": "Allergies",
        "social_history": "Social_History", "social_hx": "Social_History",
        "family_history": "Family_History", "family_hx": "Family_History",
        "conversational": "conversational",
    }
    return m.get(label.strip().lower().replace(" ", "_"), label.strip())


async def classify_one(llm: ChatOpenAI, question: str) -> str:
    resp = await llm.ainvoke([
        SystemMessage(content=CLASSIFIER_PROMPT),
        HumanMessage(content=question),
    ])
    return _normalize(resp.content)


async def classify_batch(questions: list[str], model: str, api_key: str) -> list[str]:
    llm = ChatOpenAI(model=model, api_key=api_key, temperature=0.0)
    sem = asyncio.Semaphore(5)  # gentle on rate limits

    async def bounded(q: str) -> str:
        async with sem:
            return await classify_one(llm, q)

    return await asyncio.gather(*(bounded(q) for q in questions))


def compute_metrics(y_true: list[str], y_pred: list[str]) -> dict:
    from sklearn.metrics import (
        accuracy_score, precision_recall_fscore_support, confusion_matrix,
    )
    import pandas as pd

    labels = sorted(set(y_true) | set(y_pred))
    acc = accuracy_score(y_true, y_pred)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0,
    )
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    per_domain = pd.DataFrame({
        "domain": labels,
        "precision": precision.round(3),
        "recall": recall.round(3),
        "f1": f1.round(3),
        "support": support,
    })
    cm_df = pd.DataFrame(cm, index=labels, columns=labels)
    return {"accuracy": acc, "per_domain": per_domain, "confusion_matrix": cm_df}


def plot_confusion_matrix(cm_df, out_path: str) -> None:
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(cm_df.values, cmap="Blues")
    ax.set_xticks(range(len(cm_df.columns)))
    ax.set_yticks(range(len(cm_df.index)))
    ax.set_xticklabels(cm_df.columns, rotation=45, ha="right")
    ax.set_yticklabels(cm_df.index)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Gold")
    ax.set_title("Domain Classifier Confusion Matrix")
    for i in range(len(cm_df.index)):
        for j in range(len(cm_df.columns)):
            ax.text(j, i, int(cm_df.values[i, j]),
                    ha="center", va="center",
                    color="white" if cm_df.values[i, j] > cm_df.values.max() / 2 else "black")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("labels", help="Path to labels JSONL")
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", "gpt-4o-mini"))
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY"))
    parser.add_argument("--out-dir", default="evaluation/results")
    args = parser.parse_args()

    if not args.api_key:
        raise SystemExit("OPENAI_API_KEY not set (check .env or --api-key)")

    records = load_labels(args.labels)
    if not records:
        raise SystemExit(f"No labeled records found in {args.labels}")

    questions = [r["question"] for r in records]
    y_true = [_normalize(r["gold_domain"]) for r in records]

    print(f"Classifying {len(questions)} questions with {args.model}...")
    y_pred = asyncio.run(classify_batch(questions, args.model, args.api_key))

    metrics = compute_metrics(y_true, y_pred)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Domain Classification (P2 target: ≥85% accuracy) ===")
    print(f"Accuracy: {metrics['accuracy']:.1%}  "
          f"[{'PASS' if metrics['accuracy'] >= 0.85 else 'FAIL'}]\n")
    print("Per-domain:")
    print(metrics["per_domain"].to_string(index=False))
    print("\nConfusion matrix:")
    print(metrics["confusion_matrix"])

    metrics["per_domain"].to_csv(out_dir / "domain_per_domain.csv", index=False)
    metrics["confusion_matrix"].to_csv(out_dir / "domain_confusion_matrix.csv")

    # predictions for error analysis
    with open(out_dir / "domain_predictions.jsonl", "w") as f:
        for q, gold, pred in zip(questions, y_true, y_pred):
            f.write(json.dumps({"question": q, "gold": gold, "pred": pred,
                                "correct": gold == pred}) + "\n")

    plot_confusion_matrix(metrics["confusion_matrix"],
                          str(out_dir / "domain_confusion_matrix.png"))
    print(f"\nResults saved to {out_dir}/")


if __name__ == "__main__":
    main()
