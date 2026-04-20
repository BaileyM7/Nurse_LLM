# Nurse LLM — Evaluation Framework

Offline evaluation aligned with the P2 success criteria. See `METHODOLOGY.md` for metric definitions, baselines, compute, software versions, and reproducibility notes.

## Rubric Coverage

| Rubric Ask | Where it lives |
|---|---|
| Metric definitions (↑/↓) | `METHODOLOGY.md` §1 |
| Baselines + rationale | `METHODOLOGY.md` §2, `baselines/` |
| Ablations (what drives gains) | `METHODOLOGY.md` §3, `ablations/run_ablations.py` |
| Fair comparison guarantees | `METHODOLOGY.md` §4 |
| Model / hyperparameters | `METHODOLOGY.md` §5 |
| Compute | `METHODOLOGY.md` §6 |
| Software versions | `METHODOLOGY.md` §7, `requirements.txt` |
| Reproducibility (seeds etc.) | `METHODOLOGY.md` §8 |
| Headline table w/ best + 2nd | `reports/generate_report.py` output §1 |
| Baseline comparison | same, `fidelity.csv` |
| One-sentence conclusion | same, top of report |
| Edge cases / robustness | `metrics/edge_cases.py` |
| Error analysis | `metrics/error_analysis.py` |

## Layout

```
evaluation/
├── README.md                 # this file
├── METHODOLOGY.md            # metrics, baselines, compute, reproducibility
├── requirements.txt
├── baselines/
│   ├── rule_based_patient.py   # keyword → canned (floor)
│   ├── few_shot_patient.py     # LLM only, no tracker
│   └── full_pipeline.py        # wraps app.services.llm_service
├── ablations/
│   └── run_ablations.py        # baseline_full, no_memory, temp_0, minimal_prompt
├── metrics/
│   ├── fidelity.py             # auto hallucination + character-break
│   ├── domain_classifier.py    # accuracy + confusion matrix
│   ├── engagement.py           # SQLite-backed session stats
│   ├── edge_cases.py           # adversarial inputs, pass rate per category
│   └── error_analysis.py       # worst scenarios, top hallucinations, examples
├── reports/
│   └── generate_report.py      # emits final_report.md with best/2nd-best
├── data/
│   ├── interview_script.json        # standard 20-Q assessment
│   ├── edge_cases.jsonl             # adversarial inputs
│   └── annotations/
│       └── sample_domain_labels.jsonl
└── results/                   # all CSVs, plots, and final_report.md land here
```

## Running the full evaluation

From `Nurse_LLM/` root with the conda env active:

```bash
pip install -r evaluation/requirements.txt

# 1. Baseline comparison — run all 3 systems through the interview script
python -m evaluation.runners.run_all_systems --limit 5     # sanity check
python -m evaluation.runners.run_all_systems               # full run (39 scenarios)

# 2. Compute fidelity metrics
python -m evaluation.metrics.fidelity evaluation/results/transcripts.jsonl

# 3. Error analysis (uses fidelity's per-turn output)
python -m evaluation.metrics.error_analysis evaluation/results/fidelity_details.jsonl

# 4. Domain classifier metrics (expand sample_domain_labels.jsonl first)
python -m evaluation.metrics.domain_classifier \
    evaluation/data/annotations/sample_domain_labels.jsonl

# 5. Engagement (from live SQLite)
python -m evaluation.metrics.engagement

# 6. Robustness: edge cases
python -m evaluation.metrics.edge_cases --limit 5

# 7. Ablations: what drives gains
python -m evaluation.ablations.run_ablations --limit 5
python -m evaluation.metrics.fidelity \
    evaluation/results/ablation_transcripts.jsonl \
    --out evaluation/results/ablation_fidelity.csv \
    --details-out evaluation/results/ablation_fidelity_details.jsonl

# 8. Consolidated report
python -m evaluation.reports.generate_report
open evaluation/results/final_report.md
```

## Phase 2 (needs humans)

- 100-turn manual fidelity annotation → validates auto-fidelity
- Coverage correlation vs. expert ratings
- Feedback-quality faculty rating
- User study (satisfaction, engagement in the wild)

Scaffolded under `data/annotations/`.
