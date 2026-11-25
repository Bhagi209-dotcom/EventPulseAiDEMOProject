"""SQLAlchemy ORM models for EventPulse AI."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from app.db.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class EventSession(Base):
    __tablename__ = "event_sessions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(32), unique=True, index=True, nullable=False)
    title = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    events = relationship("TelemetryEvent", back_populates="session", cascade="all, delete-orphan")
    polls = relationship("Poll", back_populates="session", cascade="all, delete-orphan")
    questions = relationship("QAQuestion", back_populates="session", cascade="all, delete-orphan")


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("event_sessions.id"), nullable=False)
    event_type = Column(String(32), nullable=False)  # reaction | dwell
    reaction = Column(String(32), nullable=True)  # positive | neutral | confused | disengaged
    dwell_seconds = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    session = relationship("EventSession", back_populates="events")


class Poll(Base):
    __tablename__ = "polls"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("event_sessions.id"), nullable=False)
    question = Column(String(300), nullable=False)
    options_json = Column(Text, nullable=False)  # JSON list of strings
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    session = relationship("EventSession", back_populates="polls")
    votes = relationship("PollVote", back_populates="poll", cascade="all, delete-orphan")


class PollVote(Base):
    __tablename__ = "poll_votes"

    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer, ForeignKey("polls.id"), nullable=False)
    option_index = Column(Integer, nullable=False)
    voter_token = Column(String(128), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    poll = relationship("Poll", back_populates="votes")


class QAQuestion(Base):
    __tablename__ = "qa_questions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("event_sessions.id"), nullable=False)
    text = Column(Text, nullable=False)
    vader_compound = Column(Float, default=0.0)
    sentiment_label = Column(String(32), default="Neutral")
    feedback_type = Column(String(64), default="General Feedback")
    created_at = Column(DateTime(timezone=True), default=utc_now)

    session = relationship("EventSession", back_populates="questions")
