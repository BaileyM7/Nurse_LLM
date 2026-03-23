from fastapi import APIRouter, HTTPException

from app.config import settings
from app.models.session import ChatRequest, ChatResponse, ChatMessage, MessageRole
from app.routers.sessions import session_manager

router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Send a student message and get the patient's response."""
    session = session_manager.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] == "ended":
        raise HTTPException(status_code=400, detail="Session has already ended")

    if session["turn_count"] >= settings.max_turns:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum turns ({settings.max_turns}) reached. Please end the session."
        )

    # Get LLM response
    from app.services.llm_service import llm_service
    patient_response = await llm_service.get_patient_response(
        request.session_id, request.message
    )

    # Record student message (in-memory)
    session["messages"].append(ChatMessage(
        role=MessageRole.STUDENT,
        content=request.message,
        domain_explored=patient_response.domain_explored,
    ))

    # Record patient response (in-memory)
    session["messages"].append(ChatMessage(
        role=MessageRole.PATIENT,
        content=patient_response.dialogue,
    ))

    session["turn_count"] += 1

    # Persist both messages to SQLite
    session_manager.save_message(
        request.session_id, "student", request.message,
        domain=patient_response.domain_explored,
    )
    session_manager.save_message(
        request.session_id, "patient", patient_response.dialogue,
    )

    # Update assessment tracker
    session["tracker"].update(
        domain_explored=patient_response.domain_explored,
        confidence=patient_response.domain_confidence,
        student_message=request.message,
    )

    return ChatResponse(
        patient_response=patient_response,
        turn_count=session["turn_count"],
        domains_covered=session["tracker"].get_covered_domains(),
    )
