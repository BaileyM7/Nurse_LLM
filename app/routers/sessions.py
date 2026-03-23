import json
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.models.session import (
    StartSessionRequest, StartSessionResponse, SessionStatus, ChatMessage, MessageRole,
)
from app.models.assessment import FeedbackReport, AssessmentResult
from app.services.scenario_service import scenario_service
from app.services.llm_service import llm_service
from app.services.assessment_service import AssessmentTracker
from app.services.feedback_service import feedback_service
from app.db.database import SessionLocal, init_db
from app.db.models import SessionRecord, MessageRecord, FeedbackRecord

router = APIRouter()

# Ensure tables exist on import
init_db()


class SessionManager:
    """Session manager with SQLite persistence.

    Active sessions live in memory (for fast access + assessment tracker state).
    All sessions and messages are also persisted to SQLite for history.
    """

    def __init__(self):
        self._active_sessions: dict[str, dict] = {}

    def create_session(self, scenario_id: str) -> dict:
        session_id = str(uuid.uuid4())[:8]
        now = datetime.utcnow()

        # In-memory state for active session
        session = {
            "session_id": session_id,
            "scenario_id": scenario_id,
            "status": "active",
            "start_time": now,
            "end_time": None,
            "messages": [],
            "turn_count": 0,
            "tracker": AssessmentTracker(),
            "feedback": None,
        }
        self._active_sessions[session_id] = session

        # Persist to SQLite
        db = SessionLocal()
        try:
            db_session = SessionRecord(
                id=session_id,
                scenario_id=scenario_id,
                status="active",
                start_time=now,
                turn_count=0,
            )
            db.add(db_session)
            db.commit()
        finally:
            db.close()

        return session

    def get_session(self, session_id: str) -> dict | None:
        return self._active_sessions.get(session_id)

    def save_message(self, session_id: str, role: str, content: str, domain: str | None = None):
        """Persist a chat message to SQLite."""
        db = SessionLocal()
        try:
            msg = MessageRecord(
                session_id=session_id,
                role=role,
                content=content,
                domain_classified=domain,
            )
            db.add(msg)
            db.commit()
        finally:
            db.close()

    def end_session(self, session_id: str, score: float | None = None):
        """Mark session as ended in SQLite."""
        db = SessionLocal()
        try:
            record = db.query(SessionRecord).filter(SessionRecord.id == session_id).first()
            if record:
                record.status = "ended"
                record.end_time = datetime.utcnow()
                record.score = score
                session = self._active_sessions.get(session_id)
                if session:
                    record.turn_count = session["turn_count"]
                db.commit()
        finally:
            db.close()

    def save_feedback(self, session_id: str, feedback: FeedbackReport):
        """Persist feedback report to SQLite."""
        db = SessionLocal()
        try:
            record = FeedbackRecord(
                session_id=session_id,
                report_json=feedback.model_dump(),
            )
            db.add(record)
            db.commit()
        finally:
            db.close()

    def list_sessions(self) -> list[dict]:
        """List all sessions from SQLite (includes completed ones from past runs)."""
        db = SessionLocal()
        try:
            records = db.query(SessionRecord).order_by(SessionRecord.start_time.desc()).all()
            result = []
            for r in records:
                # Use in-memory tracker score for active sessions, DB score for ended ones
                if r.id in self._active_sessions:
                    score = self._active_sessions[r.id]["tracker"].get_result().coverage_score
                else:
                    score = r.score or 0.0

                result.append({
                    "session_id": r.id,
                    "scenario_id": r.scenario_id,
                    "status": r.status,
                    "start_time": r.start_time.isoformat() if r.start_time else "",
                    "turn_count": r.turn_count or 0,
                    "coverage_score": score,
                })
            return result
        finally:
            db.close()

    def get_stored_feedback(self, session_id: str) -> FeedbackReport | None:
        """Retrieve feedback from SQLite for a past session."""
        db = SessionLocal()
        try:
            record = db.query(FeedbackRecord).filter(
                FeedbackRecord.session_id == session_id
            ).first()
            if record:
                return FeedbackReport(**record.report_json)
            return None
        finally:
            db.close()


# Singleton
session_manager = SessionManager()


@router.post("/start", response_model=StartSessionResponse)
async def start_session(request: StartSessionRequest):
    """Start a new assessment session with a patient scenario."""
    scenario = scenario_service.get_scenario(request.scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{request.scenario_id}' not found")

    session = session_manager.create_session(request.scenario_id)
    llm_service.start_session(session["session_id"], scenario)

    return StartSessionResponse(
        session_id=session["session_id"],
        scenario_id=scenario.patient_id,
        patient_name=scenario.name,
        chief_complaint=scenario.chief_complaint,
    )


@router.get("/{session_id}/status")
async def get_session_status(session_id: str):
    """Get current session status including assessment coverage."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    assessment = session["tracker"].get_result()
    elapsed = (datetime.utcnow() - session["start_time"]).total_seconds()

    return {
        "session_id": session_id,
        "status": session["status"],
        "turn_count": session["turn_count"],
        "elapsed_seconds": round(elapsed),
        "coverage_score": assessment.coverage_score,
        "domains_covered": assessment.get_covered_domains(),
        "domains_missed": assessment.get_missed_domains(),
        "domain_details": {
            name: {
                "covered": cov.covered,
                "question_count": cov.question_count,
            }
            for name, cov in assessment.domains.items()
        },
    }


@router.post("/{session_id}/end")
async def end_session(session_id: str):
    """End a session and generate feedback."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] == "ended":
        raise HTTPException(status_code=400, detail="Session already ended")

    session["status"] = "ended"
    session["end_time"] = datetime.utcnow()

    # Clean up LLM session
    llm_service.end_session(session_id)

    # Generate feedback
    scenario = scenario_service.get_scenario(session["scenario_id"])
    assessment = session["tracker"].get_result()

    feedback = await feedback_service.generate_feedback(
        session_id=session_id,
        scenario=scenario,
        messages=session["messages"],
        assessment=assessment,
    )
    session["feedback"] = feedback

    # Persist to SQLite
    session_manager.end_session(session_id, score=feedback.overall_score)
    session_manager.save_feedback(session_id, feedback)

    return {"status": "ended", "feedback_available": True}


@router.get("/{session_id}/feedback", response_model=FeedbackReport)
async def get_feedback(session_id: str):
    """Get the feedback report for a completed session."""
    # Check in-memory first (active session)
    session = session_manager.get_session(session_id)
    if session and session.get("feedback"):
        return session["feedback"]

    # Fall back to SQLite (past session)
    feedback = session_manager.get_stored_feedback(session_id)
    if feedback:
        return feedback

    if session and session["status"] != "ended":
        raise HTTPException(status_code=400, detail="Session is still active. End it first.")

    raise HTTPException(status_code=404, detail="Feedback not found")


@router.get("/")
async def list_sessions():
    """List all sessions (including past ones from SQLite)."""
    return session_manager.list_sessions()
