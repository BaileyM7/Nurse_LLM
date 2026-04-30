# Evaluation Methodology

Comprehensive methodology document for the Nurse LLM evaluation framework. Pairs with `README.md` (quick-start usage).

---

## 1. Metric Definitions

All metrics run offline on pre-recorded system outputs. Arrows indicate whether higher or lower is better.

| Metric | ↑/↓ | Formula | P2 Target |
|---|---|---|---|
| **Response fidelity rate** | ↑ | `faithful_turns / total_turns` | ≥ 90% |
| **Character-break rate** | ↓ | `turns_with_ai_disclosure_or_dx_advice / total_turns` | 0% ideal |
| **Hallucination rate** | ↓ | `turns_mentioning_absent_symptom / total_turns` | 0% ideal |
| **Domain classification accuracy** | ↑ | `correct_preds / total_preds` on held-out labels | ≥ 85% |
| **Per-domain F1** | ↑ | 2·P·R / (P+R) for each of 7 domains | ≥ 0.80 each |
| **Avg turns / session** | ↑ | `sum(turn_counts) / num_sessions` from SQLite | ≥ 15 |
| **Session completion rate** | ↑ | `ended_sessions / total_sessions` | ≥ 80% |
| **Edge-case pass rate** | ↑ | `handled_ok / total_edge_cases` per category | Report only |
| **Coverage correlation** (Phase 2) | ↑ | Pearson r between system coverage score and expert rating | ≥ 0.8 |
| **Feedback-quality agreement** (Phase 2) | ↑ | `items_faculty_agree / total_items` | ≥ 75% |

### How "faithful" is decided (fidelity)

A patient turn is counted as **faithful** iff:
1. No character-break pattern fires (no "As an AI", no diagnostic/treatment advice), AND
2. No hallucinated-symptom pattern fires (no affirmative mention of a symptom listed in `symptoms_absent` without a denial in the same sentence).

This is an **automatic lower bound** — it flags clear violations but will miss subtler ones (e.g., overly medical vocabulary for a layperson patient). The 100-turn manual annotation in Phase 2 will validate that auto-faithfulness tracks with human judgment.

---

## 2. Baselines & Why They're Appropriate

Three systems are compared on the same scenarios, same interview script, same scoring functions.

| System | Purpose in comparison | Why it's a good baseline |
|---|---|---|
| **Rule-based patient** | Floor | No LLM, no flexibility. Isolates *"does any LLM help at all?"* If the full pipeline doesn't beat this, something is very wrong. |
| **Few-shot LLM** | Relevant baseline | GPT-4o-mini with scenario context, but no domain classifier, no conversation memory for tracker, no feedback generator. Isolates the value added by the pipeline's *tracking/feedback* layer — if the full pipeline and few-shot baseline score identically on fidelity, then the tracker is the only differentiator worth defending. |
| **Full pipeline** | System under test | Current production behavior. |

**SOTA note.** There is no public SOTA for "simulated-patient fidelity in nursing education," so the floor + relevant baselines are the meaningful comparison. Commercial nursing sim tools (Shadow Health, iHuman) are closed-source and not accessible to this team. Cited only as context in the final report.

---

## 3. Ablations

Ablations remove one component of the full pipeline at a time to show what drives gains. Implemented in `ablations/run_ablations.py`.

| Ablation | What is removed | Hypothesis |
|---|---|---|
| `no_memory` | Per-session conversation history | Fidelity drops: patient forgets what was already said, contradicts earlier turns. |
| `no_deterministic_vitals` | `_detect_requested_vitals` / `_detect_requested_labs` regex layer in `llm_service.py` (bypassed via a wrapper) | Vitals/labs reveal is less reliable; fidelity roughly same but vitals-recall drops. |
| `temp_0` | Temperature 0.0 instead of 0.7 | Character-break rate may drop (more conservative) but personality feels flatter. |
| `minimal_prompt` | Strip personality/communication-style sections from system prompt | Fidelity roughly same; responses lose the persona, harder to tell patients apart. |

Each ablation is run through the same interview script and fed into the same fidelity scorer. The report in §8 marks the best and second-best system per metric.

---

## 4. Fair-Comparison Guarantees

- **Same scenarios.** All systems run on the same 39 scenarios (`data/scenarios/case_001..039.json`).
- **Same questions.** All systems answer the exact same 20-question script in `evaluation/data/interview_script.json`.
- **Same metric functions.** Fidelity/hallucination/break detection code is shared across systems (no system-specific scoring).
- **Same label set.** Domain classifier eval uses one labeled JSONL applied to every classifier variant.
- **Same random seed.** See §7.
- **Compute difference disclosed.** Rule-based: ~0 API calls. Few-shot: 1 call/turn. Full pipeline: 1 call/turn + 1 feedback call/session. We report API call counts and token usage alongside accuracy so any apparent quality gains can be weighed against their cost.

---

## 5. Model & Hyperparameters

Patient simulation and feedback generation share a backbone; only temperature differs.

| Component | Backbone | Temperature | Max turns | Notes |
|---|---|---|---|---|
| Patient simulation | `gpt-4o-mini` (OpenAI) | 0.7 | 30 (from `settings.max_turns`) | Structured JSON output |
| Domain classifier (inside patient sim) | `gpt-4o-mini` | 0.7 (same call) | — | Returns domain + confidence |
| Feedback generation | `gpt-4o-mini` | 0.3 | — | Lower temp for consistency |
| Conversation summary | `gpt-4o-mini` | 0.7 | trigger at 15 turns | From `settings.summary_after_turns` |

No training. This is an LLM-as-inference system; "hyperparameters" means prompting + decoding config, not gradient-descent params.

---

## 6. Compute

| Aspect | Value |
|---|---|
| Hardware | MacBook, CPU only. No GPU required. |
| Inference location | OpenAI API (gpt-4o-mini) — no local inference. |
| Memory | ~200 MB Python process; SQLite DB fits in < 50 MB at scale. |
| Wall time, full eval | ~15–25 min for 39 scenarios × 2 LLM systems × 20 questions ≈ 1,560 API calls (depends on OpenAI latency). |
| Wall time, rule-based | < 10 seconds for full run. |
| Estimated API cost | gpt-4o-mini at $0.15 / 1M input + $0.60 / 1M output tokens. Full run ≈ 400K input + 80K output tokens ≈ **$0.11**. Well under the $50/month P2 budget. |

---

## 7. Software & Versions

Minimum versions pinned in `evaluation/requirements.txt` (in addition to the core `requirements.txt`).

| Package | Version (minimum) | Used for |
|---|---|---|
| `pandas` | 2.0 | Tabular results, confusion-matrix IO |
| `scikit-learn` | 1.3 | Accuracy / P / R / F1 / confusion matrix |
| `matplotlib` | 3.7 | Confusion matrix and turn-distribution plots |
| `langchain` / `langchain-openai` | from core `requirements.txt` | Shared w/ app |
| `sqlalchemy` | 2.0 | Shared w/ app; read-only use in `engagement.py` |

---

## 8. Reproducibility

- **LLM determinism.** The domain classifier in `metrics/domain_classifier.py` uses `temperature=0.0` so repeated runs produce identical outputs modulo OpenAI's internal non-determinism. The patient simulation uses `temperature=0.7` by design — reproducibility there comes from *distribution-level* metrics (fidelity rate over hundreds of turns), not from reproducing individual turns. We report mean ± std across 3 runs in the final report.
- **Random seeds.** Python `random.seed(42)` and `numpy.random.seed(42)` set at the top of `runners/run_all_systems.py` and `ablations/run_ablations.py`. Scenarios are iterated in sorted filename order.
- **Checkpointing.** Each system × scenario transcript is written incrementally to JSONL. Both runners accept `--resume` to pick up where a partial run left off: existing transcripts are read from the output JSONL, and `(system, scenario_id)` pairs already present are skipped on the next run. Without `--resume`, the runner truncates the output file and starts from scratch.
- **Input versioning.** Scenarios and the interview script are tracked in git; the output JSONL includes `scenario_path`, `turn_index`, and `question` for full traceability back to the inputs.
- **Eval scripts are the ground truth.** Every number in the final report is produced by `reports/generate_report.py` reading from `results/*.csv` and `results/*.jsonl`. No manually transcribed numbers in slides.

---

## 9. Final Report Contents

`reports/generate_report.py` emits:

1. **Headline table** — systems as rows, metrics as cols, `**best**` bolded and `*second*` italicized per column. Metric-direction arrows in the header.
2. **Confusion matrix** — domain classifier, inline image reference.
3. **Ablation delta table** — how each ablation changes fidelity vs full pipeline.
4. **Edge-case pass rates** — per adversarial category (off-topic / diagnosis-seeking / gibberish / jailbreak).
5. **One-sentence conclusion** — auto-generated from the fidelity and accuracy numbers.
6. **Top failure examples** — 5 worst turns (verbatim student/patient pairs) for qualitative error analysis.

Outputs a single markdown file at `results/final_report.md` plus any referenced PNGs.

---

## 10. Not Claimed

- This framework does **not** claim the full pipeline is clinically safe. Faithful ≠ medically appropriate.
- We do **not** claim the interview script exhausts all ways a student might ask a question — it is a controlled comparison baseline, not a coverage guarantee.
- Auto-fidelity scores are a lower bound; Phase 2 manual annotation is the final word.

## Reproducibility

All evaluation entry points (`run_all_systems`, `run_ablations`,
`generate_plots`, `generate_report`) seed `random` (and `numpy.random` when
available) with `42` by default. Override with `--seed N` on the runners.
LLM provider calls remain non-deterministic at the model layer, but our
sampler-side seeds keep scenario ordering, sampling-based ablations, and
plot jitter stable across runs.

Both runners (`run_all_systems`, `run_ablations`) accept `--resume` to pick up
where a partial run left off: existing transcripts are read from the output JSONL,
and `(system, scenario_id)` pairs already present are skipped on the second run.
Without `--resume`, the runner truncates the output file and starts from scratch.
