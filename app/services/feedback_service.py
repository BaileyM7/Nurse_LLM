import json

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import settings
from app.models.assessment import FeedbackReport, AssessmentResult
from app.models.scenario import PatientScenario
from app.models.session import ChatMessage


FEEDBACK_PROMPT = """You are an expert nursing educator evaluating a student's patient assessment performance.

## The Patient Case
- Patient: {name}, {age}yo {sex}
- Chief complaint: {chief_complaint}
- Actual diagnosis: {diagnosis}
- Critical findings: {critical_findings}
- Expected assessment domains: {expected_domains}

## Student's Conversation
{conversation_text}

## Assessment Coverage
- Domains covered: {domains_covered}
- Domains missed: {domains_missed}
- Total assessment questions: {total_questions}

## Instructions
Evaluate the student's assessment performance and generate a detailed feedback report.
Consider:
1. Did they systematically cover the key assessment domains?
2. Did they ask follow-up questions to gather depth?
3. Did they identify the critical findings?
4. What did they do well?
5. What should they improve?

Respond with valid JSON in this exact format:
{{
    "session_id": "{session_id}",
    "overall_score": <0-100 number>,
    "domains_covered": [<list of covered domain names>],
    "domains_missed": [<list of missed domain names>],
    "strengths": [<2-4 specific things the student did well>],
    "improvements": [<2-4 specific, actionable suggestions>],
    "critical_findings_caught": [<findings the student discovered>],
    "critical_findings_missed": [<findings the student failed to discover>],
    "diagnosis": "{diagnosis}",
    "differential_diagnoses": {differential},
    "turn_highlights": [
        {{"turn": <turn number>, "student_said": "<quote>", "commentary": "<why this was good/bad>"}}
    ],
    "summary": "<2-3 sentence overall narrative>"
}}"""


class FeedbackService:
    """Generates post-session feedback reports using the LLM."""

    def __init__(self):
        self._llm = ChatOpenAI(
            model=settings.model_name,
            api_key=settings.openai_api_key,
            temperature=0.3,  # Lower temperature for more consistent evaluation
        )

    async def generate_feedback(
        self,
        session_id: str,
        scenario: PatientScenario,
        messages: list[ChatMessage],
        assessment: AssessmentResult,
    ) -> FeedbackReport:
        """Generate a structured feedback report for a completed session."""

        # Build conversation text
        conversation_lines = []
        for i, msg in enumerate(messages):
            role = "Student" if msg.role == "student" else "Patient"
            conversation_lines.append(f"Turn {i + 1} ({role}): {msg.content}")
        conversation_text = "\n".join(conversation_lines)

        prompt = FEEDBACK_PROMPT.format(
            name=scenario.name,
            age=scenario.age,
            sex=scenario.sex,
            chief_complaint=scenario.chief_complaint,
            diagnosis=scenario.rubric.diagnosis,
            critical_findings=", ".join(scenario.rubric.critical_findings),
            expected_domains=", ".join(scenario.rubric.expected_domains),
            conversation_text=conversation_text,
            domains_covered=", ".join(assessment.get_covered_domains()),
            domains_missed=", ".join(assessment.get_missed_domains()),
            total_questions=assessment.total_questions,
            session_id=session_id,
            differential=json.dumps(scenario.rubric.differential_diagnoses),
        )

        response = await self._llm.ainvoke([
            SystemMessage(content="You are a nursing education assessment expert. Always respond with valid JSON."),
            HumanMessage(content=prompt),
        ])

        try:
            data = json.loads(response.content)
            return FeedbackReport(**data)
        except (json.JSONDecodeError, Exception) as e:
            # Return a basic report if LLM output fails to parse
            return FeedbackReport(
                session_id=session_id,
                overall_score=assessment.coverage_score,
                domains_covered=assessment.get_covered_domains(),
                domains_missed=assessment.get_missed_domains(),
                diagnosis=scenario.rubric.diagnosis,
                summary=f"Feedback generation encountered an error: {str(e)}. "
                         f"You covered {len(assessment.get_covered_domains())} of 7 domains.",
            )


# Singleton
feedback_service = FeedbackService()
