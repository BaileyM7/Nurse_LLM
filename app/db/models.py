from datetime import datetime

from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.db.database import Base


class SessionRecord(Base):
    """Persisted session data."""
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    scenario_id = Column(String, nullable=False)
    status = Column(String, default="active")
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    score = Column(Float, nullable=True)
    turn_count = Column(Integer, default=0)

    messages = relationship("MessageRecord", back_populates="session", cascade="all, delete-orphan")
    feedback = relationship("FeedbackRecord", back_populates="session", uselist=False, cascade="all, delete-orphan")


class MessageRecord(Base):
    """Individual chat message."""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    role = Column(String, nullable=False)  # "student" or "patient"
    content = Column(Text, nullable=False)
    domain_classified = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("SessionRecord", back_populates="messages")


class FeedbackRecord(Base):
    """Stored feedback report."""
    __tablename__ = "feedback_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, unique=True)
    report_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("SessionRecord", back_populates="feedback")
