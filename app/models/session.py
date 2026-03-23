from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    STUDENT = "student"
    PATIENT = "patient"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """A single message in the conversation."""
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    domain_explored: str | None = Field(None, description="Assessment domain this message relates to")


class PatientResponse(BaseModel):
    """Structured output from the LLM — patient response + classification."""
    dialogue: str = Field(..., description="What the patient says to the student")
    domain_explored: str = Field(
        "conversational",
        description="Which assessment domain the student's question explored. "
        "One of: HPI, ROS, PMH, Medications, Allergies, Social_History, Family_History, "
        "Physical_Exam, Vitals, conversational"
    )
    domain_confidence: float = Field(0.0, ge=0.0, le=1.0)
    vitals_revealed: dict[str, str | float] | None = Field(
        None, description="Any vital signs revealed in this exchange"
    )
    labs_revealed: dict[str, str | float] | None = Field(
        None, description="Any lab results revealed in this exchange"
    )


class SessionStatus(str, Enum):
    ACTIVE = "active"
    ENDED = "ended"


class ChatSession(BaseModel):
    """Active chat session state."""
    session_id: str
    scenario_id: str
    status: SessionStatus = SessionStatus.ACTIVE
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: datetime | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    turn_count: int = 0


class StartSessionRequest(BaseModel):
    scenario_id: str


class StartSessionResponse(BaseModel):
    session_id: str
    scenario_id: str
    patient_name: str
    chief_complaint: str


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    patient_response: PatientResponse
    turn_count: int
    domains_covered: list[str]
