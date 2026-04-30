"""Tests for evaluation/metrics/fidelity.py.

Uses case_001 (Maria Santos) as the reference scenario. All checks are
against the pure-function API — no LLM calls.
"""

import json
from pathlib import Path

import pytest

from evaluation.metrics.fidelity import (
    check_character_break,
    check_hallucinated_symptoms,
    score_turn,
)

CASE_001_PATH = Path(__file__).parent.parent / "data" / "scenarios" / "case_001.json"


@pytest.fixture
def case_001() -> dict:
    with open(CASE_001_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# check_character_break
# ---------------------------------------------------------------------------


def test_no_character_break_clean_response(case_001):
    """A normal patient response should return no character-break hits."""
    patient_text = "I've had this chest pressure for about two hours. It feels like someone is sitting on my chest."
    hits = check_character_break(patient_text)
    assert hits == []


def test_character_break_ai_disclosure(case_001):
    """'As an AI' should trigger a character break."""
    hits = check_character_break("As an AI I cannot simulate a real patient.")
    assert len(hits) > 0


def test_character_break_diagnostic_advice(case_001):
    """Explicit treatment advice should trigger a character break."""
    hits = check_character_break("Your diagnosis is myocardial infarction.")
    assert len(hits) > 0


def test_character_break_language_model(case_001):
    """Acknowledging being a language model triggers a break."""
    hits = check_character_break("I'm a language model and cannot feel pain.")
    assert len(hits) > 0


# ---------------------------------------------------------------------------
# check_hallucinated_symptoms
# ---------------------------------------------------------------------------


def test_no_hallucination_for_present_symptoms(case_001):
    """Patient affirming a present symptom should not be flagged as hallucinated."""
    # chest_pain is in symptoms_present
    patient_text = "Yes, I have this pressure-like tightness in my chest."
    halluc = check_hallucinated_symptoms(patient_text, case_001)
    assert halluc == []


def test_hallucination_detected_for_absent_symptom(case_001):
    """Patient claiming an absent symptom affirmatively should be flagged."""
    # "headache" is in symptoms_absent for case_001
    patient_text = "I also have a terrible headache right now."
    halluc = check_hallucinated_symptoms(patient_text, case_001)
    assert "headache" in halluc


def test_denial_suppresses_hallucination_flag(case_001):
    """Denying an absent symptom should NOT be flagged as a hallucination."""
    patient_text = "No, I don't have a headache at all."
    halluc = check_hallucinated_symptoms(patient_text, case_001)
    assert "headache" not in halluc


def test_allergy_context_not_hallucinated(case_001):
    """Mentioning an absent symptom inside an allergy description should not be flagged."""
    # "rash" is in symptoms_absent; Penicillin (rash) is an allergy
    patient_text = "I'm allergic to Penicillin, it causes a rash."
    halluc = check_hallucinated_symptoms(patient_text, case_001)
    assert "rash" not in halluc


# ---------------------------------------------------------------------------
# score_turn
# ---------------------------------------------------------------------------


def test_score_turn_faithful_clean(case_001):
    """A clean patient turn should be scored faithful=True with no evidence."""
    result = score_turn(
        "I've had this tightness for about two hours. It started when I was watching TV.",
        case_001,
    )
    assert result["faithful"] is True
    assert result["character_break_evidence"] == []
    assert result["hallucinated_symptoms"] == []


def test_score_turn_unfaithful_character_break(case_001):
    """A turn with an AI-disclosure phrase should be unfaithful."""
    result = score_turn("As an AI I cannot feel chest pain.", case_001)
    assert result["faithful"] is False
    assert len(result["character_break_evidence"]) > 0


def test_score_turn_unfaithful_hallucination(case_001):
    """A turn that claims an absent symptom should be unfaithful."""
    result = score_turn("I also have a bad headache right now.", case_001)
    assert result["faithful"] is False
    assert len(result["hallucinated_symptoms"]) > 0


def test_score_turn_returns_required_keys(case_001):
    """score_turn always returns the three expected keys."""
    result = score_turn("I feel some chest pressure.", case_001)
    assert "faithful" in result
    assert "character_break_evidence" in result
    assert "hallucinated_symptoms" in result


def test_fidelity_differential_faithful_vs_unfaithful(case_001):
    """A faithful turn should score better than an unfaithful one (trivially: 1 vs 0)."""
    faithful = score_turn(
        "Yes, the pressure is in the center of my chest and it goes to my left arm.",
        case_001,
    )
    unfaithful = score_turn(
        "As an AI language model I cannot provide medical advice.",
        case_001,
    )
    # faithful should be True, unfaithful should be False
    assert faithful["faithful"] is True
    assert unfaithful["faithful"] is False
