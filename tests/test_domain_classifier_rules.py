"""Tests for the keyword-rule tier of the domain classifier.

Uses `classify_by_keywords` directly — no LLM calls, no API keys needed.
"""

import pytest

from app.services.domain_classifier import ClassificationResult, classify_by_keywords

# ---------------------------------------------------------------------------
# classify_by_keywords — parametrized happy-path cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "question,expected_domain",
    [
        # Medications
        ("Are you currently taking any medications?", "Medications"),
        ("Do you take any pills or supplements?", "Medications"),
        # Allergies
        ("Do you have any drug allergies?", "Allergies"),
        ("Are you allergic to penicillin?", "Allergies"),
        # PMH
        ("Do you have any past medical history?", "PMH"),
        ("Have you ever been hospitalized before?", "PMH"),
        ("Do you have any chronic conditions?", "PMH"),
        # Social_History
        ("Do you smoke or have you ever smoked?", "Social_History"),
        ("How much alcohol do you drink?", "Social_History"),
        ("What is your occupation?", "Social_History"),
        # Family_History
        ("Is there a family history of heart disease?", "Family_History"),
        ("Does anyone in your family have diabetes?", "Family_History"),
        # HPI
        ("When did the chest pain start?", "HPI"),
        ("On a scale of 1-10, how would you rate the pain severity?", "HPI"),
        # ROS
        ("Have you had any fever or chills?", "ROS"),
        ("Any nausea or vomiting?", "ROS"),
    ],
)
def test_keyword_matches_expected_domain(question, expected_domain):
    """classify_by_keywords should return the expected domain for clear questions."""
    result = classify_by_keywords(question)
    assert (
        expected_domain in result
    ), f"Expected {expected_domain!r} in {result} for question: {question!r}"


def test_keyword_returns_empty_for_ambiguous():
    """Completely vague input should return empty list (falls through to LLM tier)."""
    result = classify_by_keywords("Tell me more.")
    assert result == []


def test_keyword_result_is_list():
    """Return type must always be a list with at least one match for a clear question."""
    # "medication" (singular) matches \b(medication|...)\b in the Medications rules
    result = classify_by_keywords("Are you taking any medication?")
    assert isinstance(result, list)
    assert len(result) >= 1


def test_keyword_multi_label():
    """A question spanning two domains should yield both."""
    # "Do you or anyone in your family have heart disease or any medical history?"
    # should match Family_History and possibly PMH
    question = "Does anyone in your family have heart disease or past medical history?"
    result = classify_by_keywords(question)
    assert "Family_History" in result
    assert "PMH" in result


def test_keyword_case_insensitive():
    """Rules should match regardless of casing."""
    lower = classify_by_keywords("do you have any allergies?")
    upper = classify_by_keywords("DO YOU HAVE ANY ALLERGIES?")
    mixed = classify_by_keywords("Do You Have Any ALLERGIES?")
    assert "Allergies" in lower
    assert "Allergies" in upper
    assert "Allergies" in mixed


def test_keyword_does_not_match_unrelated_text():
    """A clearly unrelated question (pure greeting) should fire no keyword domains."""
    result = classify_by_keywords("Hello, how are you today?")
    assert result == []


def test_classification_result_dataclass():
    """ClassificationResult should hold domains, confidence, and source."""
    cr = ClassificationResult(domains=["HPI"], confidence=0.95, source="keyword")
    assert cr.domains == ["HPI"]
    assert cr.confidence == 0.95
    assert cr.source == "keyword"
