"""Few-shot LLM baseline: 3-shot prompt + scenario context, no tracker or feedback."""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.models.scenario import PatientScenario

FEW_SHOT_SYSTEM = """You are a simulated patient. Stay in character. Only mention \
symptoms, history, vitals, and labs that appear in the scenario below. If asked \
about something not listed, deny it. Respond in 1-3 sentences using plain language.

### Scenario
{scenario_json}

### Example turns
Student: What brings you in today?
Patient: {example_cc}

Student: Do you have any allergies?
Patient: {example_allergy}

Student: Any family history of heart problems?
Patient: {example_fam}
"""


def _example_allergy(scenario: PatientScenario) -> str:
    if scenario.allergies:
        return "Yes, I'm allergic to " + scenario.allergies[0] + "."
    return "No known allergies."


def _example_fam(scenario: PatientScenario) -> str:
    conds = scenario.family_history.conditions
    if conds:
        m, c = next(iter(conds.items()))
        return f"My {m} had {c}."
    return "Nothing I know of."


class FewShotPatient:
    def __init__(self, scenario: PatientScenario):
        self.scenario = scenario
        self._llm = ChatOpenAI(
            model=settings.model_name,
            api_key=settings.openai_api_key,
            temperature=0.7,
        )
        # Serialize a trimmed scenario to keep the prompt compact
        trimmed = {
            "name": scenario.name,
            "age": scenario.age,
            "sex": scenario.sex,
            "chief_complaint": scenario.chief_complaint,
            "onset": scenario.onset_description,
            "symptoms_present": {
                k: v.description for k, v in scenario.symptoms_present.items()
            },
            "symptoms_absent": scenario.symptoms_absent,
            "pmh": scenario.past_medical_history,
            "medications": scenario.medications,
            "allergies": scenario.allergies,
            "social": scenario.social_history.model_dump(exclude_none=True),
            "family": scenario.family_history.conditions,
            "vitals": scenario.vitals.model_dump(exclude_none=True),
            "labs": scenario.labs,
        }
        self._system = FEW_SHOT_SYSTEM.format(
            scenario_json=json.dumps(trimmed, indent=2),
            example_cc=scenario.chief_complaint,
            example_allergy=_example_allergy(scenario),
            example_fam=_example_fam(scenario),
        )
        self._history: list = []

    async def respond(self, student_message: str) -> str:
        messages = (
            [SystemMessage(content=self._system)]
            + self._history
            + [HumanMessage(content=student_message)]
        )
        resp = await self._llm.ainvoke(messages)
        self._history.append(HumanMessage(content=student_message))
        self._history.append(AIMessage(content=resp.content))
        return resp.content
