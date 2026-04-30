"""
Full pipeline adapter: wraps the existing app.services.llm_service.LLMService so
the evaluation runner has a uniform interface across all three systems.

Does NOT modify the app — only imports from it.
"""

from __future__ import annotations

import uuid

from app.models.scenario import PatientScenario
from app.services.llm_service import LLMService


class FullPipelinePatient:
    def __init__(self, scenario: PatientScenario):
        self.scenario = scenario
        self._service = LLMService()
        self._session_id = f"eval-{uuid.uuid4()}"
        self._service.start_session(self._session_id, scenario)

    async def respond(self, student_message: str) -> str:
        resp = await self._service.get_patient_response(
            self._session_id, student_message
        )
        return resp.dialogue

    def close(self) -> None:
        self._service.end_session(self._session_id)
