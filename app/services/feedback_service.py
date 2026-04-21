import json

from langchain_core.messages import SystemMessage, HumanMessage

from app.config import settings
from app.models.assessment import FeedbackReport, AssessmentResult
from app.models.scenario import PatientScenario
from app.models.session import ChatMessage
from app.services.llm_provider import create_feedback_model, supports_json_mode


FEEDBACK_PROMPT = """You are an expert nursing educator evaluating a student's patient assessment performance.

## The Patient Case
- Patient: {name}, {age}yo {sex}
- Chief complaint: {chief_complaint}
- Actual diagnosis: {diagnosis}
- Critical findings: {critical_findings}
- Expected assessment domains: {expected_domains}

## Student's Conversation (numbered turns)
{conversation_text}

## Assessment Coverage
- Domains covered: {domains_covered}
- Domains missed: {domains_missed}
- Depth breakdown: {depth_breakdown}
- Total assessment questions: {total_questions}

## Evaluation Rules — READ CAREFULLY
**Every strength, improvement, and critical-finding observation MUST be grounded in a specific turn from the transcript above.**

- For every bullet in `strengths` and `improvements`, reference the turn number like "(Turn N)" and quote the student's exact words.
- If you cannot cite a specific turn, don't make the observation. Generic advice like "ask more questions" is forbidden — name the missing question.
- In `turn_highlights`, each entry MUST have an accurate `turn` number and `student_said` quote taken verbatim from the transcript.
- If the student used vague questions like "tell me more", flag this in improvements and cite the exact turn.
- Do not invent quotes. If you can't find a supporting quote, omit the observation.

## Good Examples
GOOD strength: "Asked about radiation of chest pain (Turn 4: 'Does the pain spread anywhere?') — this is essential for ruling out cardiac vs. musculoskeletal causes."
BAD strength: "Good job asking about symptoms" — too vague, no citation.

GOOD improvement: "Missed asking about family cardiac history despite patient's age and chest pain presentation. At Turn 8 ('Any other questions I should answer?') was an opening to explore this."
BAD improvement: "Should ask more follow-up questions" — generic, no citation.

## Output Format
Respond with valid JSON in this exact format:
{{
    "session_id": "{session_id}",
    "overall_score": <0-100 number, calibrated to depth-weighted coverage + critical-finding discovery>,
    "domains_covered": [<list of covered domain names>],
    "domains_missed": [<list of missed domain names>],
    "strengths": [<2-4 specific quote-grounded observations, each with "(Turn N: 'quote')">],
    "improvements": [<2-4 specific quote-grounded suggestions, each citing a turn>],
    "critical_findings_caught": [<findings the student discovered, reference turn numbers>],
    "critical_findings_missed": [<findings not discovered, with suggested questions that would have uncovered them>],
    "diagnosis": "{diagnosis}",
    "differential_diagnoses": {differential},
    "turn_highlights": [
        {{"turn": <turn number>, "student_said": "<exact quote>", "commentary": "<why this mattered>"}}
    ],
    "summary": "<2-3 sentence narrative referencing at least one specific turn>"
}}"""


class FeedbackService:
    """Generates post-session feedback reports using a high-quality model.

    Uses the configured provider's quality tier (gpt-4o or gemini-1.5-pro)
    because feedback is the student-facing deliverable — worth the extra cost
    for one call per session.
    """

    def __init__(self):
        # Provider-agnostic quality tier — gpt-4o for OpenAI, gemini-1.5-pro for Gemini
        self._llm = create_feedback_model(temperature=0.3)

    async def generate_feedback(
        self,
        session_id: str,
        scenario: PatientScenario,
        messages: list[ChatMessage],
        assessment: AssessmentResult,
    ) -> FeedbackReport:
        """Generate a structured feedback report for a completed session."""

        # Build conversation text — use student turn numbers only (1, 2, 3...)
        # so citations in feedback match what the student sees in the UI.
        conversation_lines = []
        student_turn = 0
        for msg in messages:
            if msg.role == "student":
                student_turn += 1
                conversation_lines.append(f"Turn {student_turn} (Student): {msg.content}")
            else:
                conversation_lines.append(f"         (Patient): {msg.content}")
        conversation_text = "\n".join(conversation_lines)

        # Build depth breakdown string: "HPI: Deep, ROS: Surface, ..."
        depth_breakdown = ", ".join(
            f"{d}: {cov.depth}" for d, cov in assessment.domains.items()
        )

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
            depth_breakdown=depth_breakdown,
            total_questions=assessment.total_questions,
            session_id=session_id,
            differential=json.dumps(scenario.rubric.differential_diagnoses),
        )

        # OpenAI supports `response_format={"type": "json_object"}` as a runtime bind.
        # Gemini doesn't — it uses `response_mime_type` at construction time.
        # For Gemini we rely on the prompt + markdown-fence stripping below.
        llm = self._llm.bind(response_format={"type": "json_object"}) if supports_json_mode() else self._llm

        response = await llm.ainvoke([
            SystemMessage(content="You are a nursing education assessment expert. Always respond with valid JSON. Every observation must cite a specific turn number and quote the student verbatim."),
            HumanMessage(content=prompt),
        ])

        content = response.content.strip()
        # Strip markdown fences if the model added them anyway
        if content.startswith("```"):
            content = content.split("```", 2)[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.rsplit("```", 1)[0].strip()

        try:
            data = json.loads(content)
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
