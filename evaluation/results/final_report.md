# Nurse LLM — Evaluation Report

_Auto-generated from metric outputs. Do not hand-edit._

## Conclusion

**Full pipeline** achieved 99.0% response fidelity (P2 target ≥90%: MET) — note that rule_based scored higher on faithfulness, suggesting the tracking/feedback layer is not hurting, but is not driving fidelity gains.

## 1. Headline: Response Fidelity

| System | Faithful ↑ | Char-break ↓ | Halluc. ↓ | Turns |
|---|---|---|---|---|
| rule_based | **100.0%** | **0.0%** | **0.0%** | 100 |
| few_shot | *99.0%* | 1.0% | *0.0%* | 100 |
| full_pipeline | 99.0% | *0.0%* | 1.0% | 100 |

↑ = higher is better, ↓ = lower is better. **bold** = best, *italic* = second-best.

## 2. Domain Classification

_Run `python -m evaluation.metrics.domain_classifier <labels.jsonl>` first._

## 3. Ablations: What Drives Fidelity?

| Variant | Faithful | Δ vs baseline | Char-break | Halluc. |
|---|---|---|---|---|
| baseline_full | 90.0% | +0.0% | 0.0% | 10.0% |
| no_memory | 80.0% | -10.0% | 0.0% | 20.0% |
| temp_0 | 80.0% | -10.0% | 0.0% | 20.0% |
| minimal_prompt | 95.0% | +5.0% | 0.0% | 5.0% |

## 4. Robustness: Edge-Case Pass Rates

| Category | few_shot | full_pipeline | rule_based |
|---|---|---|---|
| absent_symptom_probe | 100.0% | 100.0% | 100.0% |
| diagnosis_seeking | 100.0% | 100.0% | 100.0% |
| gibberish | 100.0% | 100.0% | 100.0% |
| jailbreak | 100.0% | 100.0% | 100.0% |
| off_topic | 100.0% | 100.0% | 100.0% |

## 5. Qualitative Error Examples

### few_shot

**Scenario:** `case_001`  
**Student:** Are there any medical conditions that run in your family?  
**Patient:** Yes, my father had a myocardial infarction at age 55 and died at 62 from heart failure. My mother has type 2 diabetes and hypertension, and she's alive at 89. My brother has hypertension and high cholesterol.  
**Break:** myocardial infarction  

### full_pipeline

**Scenario:** `case_002`  
**Student:** Do you have any drug or food allergies?  
**Patient:** I'm allergic to sulfa drugs. I get a severe rash and swelling.  
**Hallucinated:** rash  


## Reproducibility

- Random seed: 42 (set in `run_all_systems.py` and `ablations/run_ablations.py`)
- Classifier temperature: 0.0. Patient simulation: 0.7.
- See `evaluation/METHODOLOGY.md` for full methodology.
