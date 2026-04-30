import uuid
from datetime import datetime

from app.db.database import SessionLocal, init_db
from app.db.models import FeedbackRecord, MessageRecord, SessionRecord
from app.models.assessment import FeedbackReport
from app.services.assessment_service import AssessmentTracker

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

    def save_message(
        self, session_id: str, role: str, content: str, domain: str | None = None
    ):
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
            record = (
                db.query(SessionRecord).filter(SessionRecord.id == session_id).first()
            )
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
            records = (
                db.query(SessionRecord).order_by(SessionRecord.start_time.desc()).all()
            )
            result = []
            for r in records:
                if r.id in self._active_sessions:
                    score = (
                        self._active_sessions[r.id]["tracker"]
                        .get_result()
                        .coverage_score
                    )
                else:
                    score = r.score or 0.0

                result.append(
                    {
                        "session_id": r.id,
                        "scenario_id": r.scenario_id,
                        "status": r.status,
                        "start_time": r.start_time.isoformat() if r.start_time else "",
                        "turn_count": r.turn_count or 0,
                        "coverage_score": score,
                    }
                )
            return result
        finally:
            db.close()

    def get_stored_feedback(self, session_id: str) -> FeedbackReport | None:
        """Retrieve feedback from SQLite for a past session."""
        db = SessionLocal()
        try:
            record = (
                db.query(FeedbackRecord)
                .filter(FeedbackRecord.session_id == session_id)
                .first()
            )
            if record:
                return FeedbackReport(**record.report_json)
            return None
        finally:
            db.close()


# Singleton
session_manager = SessionManager()
