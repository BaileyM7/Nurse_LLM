from fastapi import APIRouter, HTTPException

from app.config import settings
from app.models.session import ChatMessage, ChatRequest, ChatResponse, MessageRole
from app.services.domain_classifier import domain_classifier
from app.services.session_manager import session_manager

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
            detail=f"Maximum turns ({settings.max_turns}) reached. Please end the session.",
        )

    # Classify the student's question (keyword rules first, LLM fallback)
    classification = await domain_classifier.classify(request.message)
    primary_domain = (
        classification.domains[0] if classification.domains else "conversational"
    )

    # Get LLM response (patient simulation — still generates dialogue)
    from app.services.llm_service import llm_service

    patient_response = await llm_service.get_patient_response(
        request.session_id, request.message
    )

    # Override the patient sim's self-reported classification with our dedicated classifier
    patient_response.domain_explored = primary_domain
    patient_response.domain_confidence = classification.confidence

    # Record student message (in-memory)
    session["messages"].append(
        ChatMessage(
            role=MessageRole.STUDENT,
            content=request.message,
            domain_explored=primary_domain,
        )
    )

    # Record patient response (in-memory)
    session["messages"].append(
        ChatMessage(
            role=MessageRole.PATIENT,
            content=patient_response.dialogue,
        )
    )

    session["turn_count"] += 1

    # Persist both messages to SQLite
    session_manager.save_message(
        request.session_id,
        "student",
        request.message,
        domain=primary_domain,
    )
    session_manager.save_message(
        request.session_id,
        "patient",
        patient_response.dialogue,
    )

    # Update assessment tracker with multi-label domains
    session["tracker"].update(
        domains=classification.domains,
        confidence=classification.confidence,
        student_message=request.message,
    )

    return ChatResponse(
        patient_response=patient_response,
        turn_count=session["turn_count"],
        domains_covered=session["tracker"].get_covered_domains(),
    )
