from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.models.assessment import FeedbackReport
from app.models.session import (
    StartSessionRequest,
    StartSessionResponse,
)
from app.services.feedback_service import feedback_service
from app.services.llm_service import llm_service
from app.services.scenario_service import scenario_service
from app.services.session_manager import session_manager

router = APIRouter()


@router.post("/start", response_model=StartSessionResponse)
async def start_session(request: StartSessionRequest):
    """Start a new assessment session with a patient scenario."""
    scenario = scenario_service.get_scenario(request.scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=404, detail=f"Scenario '{request.scenario_id}' not found"
        )

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
        raise HTTPException(
            status_code=400, detail="Session is still active. End it first."
        )

    raise HTTPException(status_code=404, detail="Feedback not found")


@router.get("/")
async def list_sessions():
    """List all sessions (including past ones from SQLite)."""
    return session_manager.list_sessions()
