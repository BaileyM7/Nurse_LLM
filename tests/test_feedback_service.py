"""Tests for FeedbackService with a mocked LLM client.

The service calls self._llm.bind(...).ainvoke(...) (OpenAI path) or
self._llm.ainvoke(...) (Gemini path). We patch `create_feedback_model` at
import time so the singleton is never constructed with real credentials.
"""

import json
from unittest.mock import patch

import pytest

import app.services.feedback_service as feedback_service_module
from app.models.assessment import ASSESSMENT_DOMAINS, AssessmentResult, DomainCoverage
from app.models.session import ChatMessage, MessageRole


def _make_assessment(domains_covered=None) -> AssessmentResult:
    """Build a minimal AssessmentResult with some domains covered."""
    domains_covered = domains_covered or ["HPI", "PMH"]
    result = AssessmentResult(
        domains={
            d: DomainCoverage(
                domain=d,
                covered=(d in domains_covered),
                question_count=2 if d in domains_covered else 0,
            )
            for d in ASSESSMENT_DOMAINS
        },
        coverage_score=22.9,
        total_questions=len(domains_covered) * 2,
    )
    return result


def _make_messages() -> list:
    return [
        ChatMessage(
            role=MessageRole.STUDENT, content="When did your chest pain start?"
        ),
        ChatMessage(role=MessageRole.PATIENT, content="About two hours ago."),
        ChatMessage(
            role=MessageRole.STUDENT, content="Do you have any past medical history?"
        ),
        ChatMessage(
            role=MessageRole.PATIENT,
            content="Yes, I have high blood pressure and diabetes.",
        ),
    ]


def _canned_feedback_json(session_id: str) -> str:
    return json.dumps(
        {
            "session_id": session_id,
            "overall_score": 45.0,
            "domains_covered": ["HPI", "PMH"],
            "domains_missed": [
                "ROS",
                "Medications",
                "Allergies",
                "Social_History",
                "Family_History",
            ],
            "strengths": [
                "Asked about onset (Turn 1: 'When did your chest pain start?') — good HPI opening."
            ],
            "improvements": [
                "Missed medications domain entirely — should ask about current prescriptions."
            ],
            "critical_findings_caught": ["Chest pain onset identified."],
            "critical_findings_missed": ["Did not explore radiation of chest pain."],
            "diagnosis": "NSTEMI (Non-ST Elevation Myocardial Infarction)",
            "differential_diagnoses": ["Unstable angina", "STEMI"],
            "turn_highlights": [
                {
                    "turn": 1,
                    "student_said": "When did your chest pain start?",
                    "commentary": "Good opening HPI question.",
                }
            ],
            "summary": "The student covered basic HPI and PMH but missed 5 of 7 domains.",
        }
    )


@pytest.mark.asyncio
async def test_generate_feedback_parses_llm_json(sample_scenario):
    """FeedbackService should parse a well-formed JSON LLM response into FeedbackReport."""
    session_id = "test-session-001"
    canned_json = _canned_feedback_json(session_id)
    assessment = _make_assessment(["HPI", "PMH"])
    messages = _make_messages()

    # Build a stub LLM that returns our canned JSON
    class _FakeMsg:
        content = canned_json

    class _FakeLLM:
        def bind(self, **_):
            return self

        async def ainvoke(self, *_a, **_k):
            return _FakeMsg()

    # Patch create_feedback_model so the FeedbackService singleton uses our stub
    with patch.object(
        feedback_service_module, "create_feedback_model", return_value=_FakeLLM()
    ), patch.object(feedback_service_module, "supports_json_mode", return_value=True):
        service = feedback_service_module.FeedbackService()
        report = await service.generate_feedback(
            session_id=session_id,
            scenario=sample_scenario,
            messages=messages,
            assessment=assessment,
        )

    assert report.session_id == session_id
    assert report.overall_score == 45.0
    assert "HPI" in report.domains_covered
    assert "PMH" in report.domains_covered
    assert len(report.strengths) >= 1
    assert len(report.improvements) >= 1
    assert "NSTEMI" in report.diagnosis


@pytest.mark.asyncio
async def test_generate_feedback_fallback_on_bad_json(sample_scenario):
    """If the LLM returns malformed JSON, FeedbackService should return a fallback report."""
    session_id = "test-session-002"
    assessment = _make_assessment(["HPI"])
    messages = _make_messages()

    class _FakeBadMsg:
        content = "This is NOT valid JSON at all!!!"

    class _FakeLLM:
        def bind(self, **_):
            return self

        async def ainvoke(self, *_a, **_k):
            return _FakeBadMsg()

    with patch.object(
        feedback_service_module, "create_feedback_model", return_value=_FakeLLM()
    ), patch.object(feedback_service_module, "supports_json_mode", return_value=True):
        service = feedback_service_module.FeedbackService()
        report = await service.generate_feedback(
            session_id=session_id,
            scenario=sample_scenario,
            messages=messages,
            assessment=assessment,
        )

    # Fallback report should still have the session_id and diagnosis
    assert report.session_id == session_id
    assert report.diagnosis == sample_scenario.rubric.diagnosis
    # Coverage score from the assessment object
    assert report.overall_score == assessment.coverage_score


@pytest.mark.asyncio
async def test_generate_feedback_strips_markdown_fences(sample_scenario):
    """Service should strip ```json ... ``` fences before parsing."""
    session_id = "test-session-003"
    canned_json = _canned_feedback_json(session_id)
    wrapped = f"```json\n{canned_json}\n```"
    assessment = _make_assessment(["HPI", "PMH"])
    messages = _make_messages()

    class _FakeFencedMsg:
        content = wrapped

    class _FakeLLM:
        def bind(self, **_):
            return self

        async def ainvoke(self, *_a, **_k):
            return _FakeFencedMsg()

    with patch.object(
        feedback_service_module, "create_feedback_model", return_value=_FakeLLM()
    ), patch.object(feedback_service_module, "supports_json_mode", return_value=True):
        service = feedback_service_module.FeedbackService()
        report = await service.generate_feedback(
            session_id=session_id,
            scenario=sample_scenario,
            messages=messages,
            assessment=assessment,
        )

    # Should parse successfully despite fences
    assert report.session_id == session_id
    assert report.overall_score == 45.0


@pytest.mark.asyncio
async def test_generate_feedback_domains_missed(sample_scenario):
    """domains_missed in the report should reflect what the assessment tracked."""
    session_id = "test-session-004"
    canned_json = _canned_feedback_json(session_id)
    assessment = _make_assessment(["HPI", "PMH"])
    messages = _make_messages()

    class _FakeMsg:
        content = canned_json

    class _FakeLLM:
        def bind(self, **_):
            return self

        async def ainvoke(self, *_a, **_k):
            return _FakeMsg()

    with patch.object(
        feedback_service_module, "create_feedback_model", return_value=_FakeLLM()
    ), patch.object(feedback_service_module, "supports_json_mode", return_value=True):
        service = feedback_service_module.FeedbackService()
        report = await service.generate_feedback(
            session_id=session_id,
            scenario=sample_scenario,
            messages=messages,
            assessment=assessment,
        )

    # The canned JSON has 5 missed domains
    assert len(report.domains_missed) == 5
    assert "Medications" in report.domains_missed
