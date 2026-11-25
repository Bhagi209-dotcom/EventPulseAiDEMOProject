"""FastAPI REST & WebSocket routes for EventPulse AI."""
import json
import random
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.db.database import get_db
from app.db.models import EventSession, TelemetryEvent, Poll, PollVote, QAQuestion
from app.services.sanitizer import sanitize_text, classify_qa_feedback
from app.services.ml_engine import ml_engine
from app.ws.manager import ws_manager

router = APIRouter()
_analyzer = SentimentIntensityAnalyzer()


class SessionCreate(BaseModel):
    code: str
    title: str


class ReactionIn(BaseModel):
    session_code: str = "DEMO-101"
    reaction: str  # positive | neutral | confused | disengaged


class DwellIn(BaseModel):
    session_code: str = "DEMO-101"
    dwell_seconds: float


class PollCreate(BaseModel):
    session_code: str = "DEMO-101"
    question: str
    options: List[str]


class PollVoteIn(BaseModel):
    option_index: int
    voter_token: Optional[str] = None


class QAIn(BaseModel):
    session_code: str = "DEMO-101"
    text: str


class DemoSimulateIn(BaseModel):
    session_code: str = "DEMO-101"
    mode: str = "engaged"  # engaged | confusion_spike | disengagement_drift


def _get_session(db: Session, code: str) -> EventSession:
    sess = db.query(EventSession).filter(EventSession.code == code).first()
    if not sess:
        raise HTTPException(status_code=404, detail=f"Session {code} not found")
    return sess


def compute_session_telemetry(db: Session, sess: EventSession) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=3)
    events = (
        db.query(TelemetryEvent)
        .filter(TelemetryEvent.session_id == sess.id)
        .order_by(TelemetryEvent.created_at.desc())
        .limit(200)
        .all()
    )
    reactions = [e for e in events if e.event_type == "reaction"]
    dwells = [e.dwell_seconds for e in events if e.event_type == "dwell" and e.dwell_seconds > 0]

    total_r = max(len(reactions), 1)
    pos_c = sum(1 for r in reactions if r.reaction == "positive")
    neu_c = sum(1 for r in reactions if r.reaction == "neutral")
    conf_c = sum(1 for r in reactions if r.reaction == "confused")
    dis_c = sum(1 for r in reactions if r.reaction == "disengaged")

    pos_ratio = pos_c / total_r
    conf_ratio = conf_c / total_r
    dis_ratio = dis_c / total_r
    avg_dwell = sum(dwells) / len(dwells) if dwells else 120.0

    questions = (
        db.query(QAQuestion)
        .filter(QAQuestion.session_id == sess.id)
        .order_by(QAQuestion.created_at.desc())
        .limit(30)
        .all()
    )
    avg_compound = (
        sum(q.vader_compound for q in questions) / len(questions)
        if questions
        else (pos_ratio - dis_ratio - 0.3 * conf_ratio)
    )

    polls = db.query(Poll).filter(Poll.session_id == sess.id).all()
    total_votes = sum(len(p.votes) for p in polls)
    poll_rate = min(1.0, total_votes / max(total_r, 10)) if polls else 0.65

    features = {
        "vader_compound": avg_compound,
        "vader_pos": max(0.0, pos_ratio),
        "vader_neg": max(0.0, dis_ratio + 0.3 * conf_ratio),
        "vader_neu": max(0.0, neu_c / total_r),
        "text_length": 85.0,
        "word_count": 15.0,
        "question_mark_count": float(sum(1 for q in questions if "?" in q.text)),
        "exclamation_count": 1.0,
        "improvement_suggestion": 1.0 if dis_ratio > 0.25 else 0.0,
        "qa_intent": 1.0 if len(questions) > 0 else 0.0,
        "experience_sharing": 1.0 if pos_ratio > 0.5 else 0.0,
        "technical_feedback": 1.0 if conf_ratio > 0.25 else 0.0,
        "support_request": 1.0 if conf_ratio > 0.35 else 0.0,
        "community_interaction": 1.0 if poll_rate > 0.5 else 0.0,
        "not_praise": 1.0 if (dis_ratio + conf_ratio) > 0.4 else 0.0,
        "reactions_per_min": float(len(reactions)) / 3.0,
        "confused_ratio": conf_ratio,
        "disengaged_ratio": dis_ratio,
        "positive_ratio": pos_ratio,
        "avg_dwell_seconds": avg_dwell,
        "poll_participation_rate": poll_rate,
        "qa_velocity_3m": float(len(questions)),
        "sentiment_delta_3m": avg_compound * 0.2,
        "window_latency_ms": 14.5,
    }

    prediction = ml_engine.predict_with_shap(features)
    risk_actions = {
        "Low": "Keep current pace; audience is engaged.",
        "Moderate": "Check in with a quick poll or recap key point.",
        "High": "Slow down, pause for Q&A, and clarify recent concepts.",
        "Critical": "Immediate reset: switch to interactive example or break.",
    }
    prediction["recommended_action"] = risk_actions.get(
        prediction.get("risk_level", "Low"),
        "Monitor audience feedback and adjust pace as needed.",
    )

    poll_list = []
    for p in reversed(polls[-5:]):
        opts = json.loads(p.options_json)
        counts = [0] * len(opts)
        for v in p.votes:
            if 0 <= v.option_index < len(counts):
                counts[v.option_index] += 1
        poll_list.append({
            "id": p.id,
            "question": p.question,
            "options": opts,
            "counts": counts,
            "total_votes": sum(counts),
            "is_active": p.is_active,
        })

    qa_list = []
    for q in questions[:15]:
        cls = classify_qa_feedback(q.text, q.vader_compound)
        qa_list.append({
            "id": q.id,
            "text": q.text,
            "vader_compound": round(q.vader_compound, 3),
            "sentiment_label": cls["sentiment_label"],
            "feedback_type": cls["feedback_type"],
            "nlp_explanation": cls["nlp_explanation"],
        })

    return {
        "session_code": sess.code,
        "session_title": sess.title,
        "counts": {
            "positive": pos_c,
            "neutral": neu_c,
            "confused": conf_c,
            "disengaged": dis_c,
            "total_reactions": len(reactions),
        },
        "metrics": {
            "reactions_per_min": round(len(reactions) / 3.0, 1),
            "avg_dwell_seconds": round(avg_dwell, 1),
            "sentiment_score": round(avg_compound, 3),
            "poll_participation_rate": round(poll_rate * 100.0, 1),
        },
        "prediction": prediction,
        "polls": poll_list,
        "qa": qa_list,
    }


@router.post("/api/v1/sessions")
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    existing = db.query(EventSession).filter(EventSession.code == payload.code).first()
    if existing:
        return {"code": existing.code, "title": existing.title, "id": existing.id}
    sess = EventSession(code=payload.code, title=payload.title, is_active=True)
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return {"code": sess.code, "title": sess.title, "id": sess.id}


@router.get("/api/v1/sessions/active")
def get_active_session(code: str = "DEMO-101", db: Session = Depends(get_db)):
    sess = _get_session(db, code)
    return compute_session_telemetry(db, sess)


@router.post("/api/v1/events/react")
async def post_reaction(payload: ReactionIn, db: Session = Depends(get_db)):
    sess = _get_session(db, payload.session_code)
    ev = TelemetryEvent(session_id=sess.id, event_type="reaction", reaction=payload.reaction)
    db.add(ev)
    db.commit()
    snapshot = compute_session_telemetry(db, sess)
    await ws_manager.broadcast(sess.code, {"type": "telemetry_update", "data": snapshot})
    return snapshot


@router.post("/api/v1/events/dwell")
async def post_dwell(payload: DwellIn, db: Session = Depends(get_db)):
    sess = _get_session(db, payload.session_code)
    ev = TelemetryEvent(session_id=sess.id, event_type="dwell", dwell_seconds=payload.dwell_seconds)
    db.add(ev)
    db.commit()
    snapshot = compute_session_telemetry(db, sess)
    await ws_manager.broadcast(sess.code, {"type": "telemetry_update", "data": snapshot})
    return snapshot


@router.post("/api/v1/polls")
async def create_poll(payload: PollCreate, db: Session = Depends(get_db)):
    sess = _get_session(db, payload.session_code)
    clean_q = sanitize_text(payload.question)
    clean_opts = [sanitize_text(o) for o in payload.options if sanitize_text(o)]
    poll = Poll(session_id=sess.id, question=clean_q, options_json=json.dumps(clean_opts))
    db.add(poll)
    db.commit()
    snapshot = compute_session_telemetry(db, sess)
    await ws_manager.broadcast(sess.code, {"type": "telemetry_update", "data": snapshot})
    return snapshot


@router.post("/api/v1/polls/{poll_id}/vote")
async def vote_poll(poll_id: int, payload: PollVoteIn, db: Session = Depends(get_db)):
    poll = db.query(Poll).filter(Poll.id == poll_id).first()
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")
    if payload.voter_token:
        existing = (
            db.query(PollVote)
            .filter(PollVote.poll_id == poll.id, PollVote.voter_token == payload.voter_token)
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Already voted in this poll")
    vote = PollVote(
        poll_id=poll.id,
        option_index=payload.option_index,
        voter_token=payload.voter_token,
    )
    db.add(vote)
    db.commit()
    sess = db.query(EventSession).filter(EventSession.id == poll.session_id).first()
    snapshot = compute_session_telemetry(db, sess)
    await ws_manager.broadcast(sess.code, {"type": "telemetry_update", "data": snapshot})
    return snapshot


@router.get("/api/v1/network/info")
def get_network_info():
    import socket

    lan_ip = "127.0.0.1"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            lan_ip = s.getsockname()[0]
    except Exception:
        try:
            lan_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            lan_ip = "127.0.0.1"
    return {"lan_ip": lan_ip}


@router.post("/api/v1/qa")
async def post_qa(payload: QAIn, db: Session = Depends(get_db)):
    sess = _get_session(db, payload.session_code)
    clean_text = sanitize_text(payload.text)
    if not clean_text:
        raise HTTPException(status_code=400, detail="Empty question after sanitization")
    compound = float(_analyzer.polarity_scores(clean_text)["compound"])
    cls = classify_qa_feedback(clean_text, compound)
    q = QAQuestion(
        session_id=sess.id,
        text=clean_text,
        vader_compound=compound,
        sentiment_label=cls["sentiment_label"],
        feedback_type=cls["feedback_type"],
    )
    db.add(q)
    db.commit()
    snapshot = compute_session_telemetry(db, sess)
    await ws_manager.broadcast(sess.code, {"type": "telemetry_update", "data": snapshot})
    return snapshot


@router.post("/api/v1/demo/simulate")
async def simulate_audience(payload: DemoSimulateIn, db: Session = Depends(get_db)):
    sess = _get_session(db, payload.session_code)
    mode = payload.mode

    if mode == "engaged":
        weights = [("positive", 12), ("neutral", 4), ("confused", 1), ("disengaged", 1)]
        dwell_range = (120.0, 190.0)
        sample_qa = "Great explanation of the architecture! Can we see the live benchmark?"
    elif mode == "confusion_spike":
        weights = [("confused", 12), ("neutral", 3), ("positive", 2), ("disengaged", 2)]
        dwell_range = (70.0, 115.0)
        sample_qa = "Wait, I am confused about how Platt scaling calibrates the CatBoost probabilities?"
    elif mode == "disengagement_drift":
        weights = [("disengaged", 14), ("confused", 3), ("neutral", 2), ("positive", 1)]
        dwell_range = (15.0, 45.0)
        sample_qa = "This is moving too slow and feels repetitive, losing focus."
    else:
        raise HTTPException(status_code=400, detail="Invalid simulation mode")

    for reaction, count in weights:
        for _ in range(count):
            db.add(TelemetryEvent(session_id=sess.id, event_type="reaction", reaction=reaction))
    for _ in range(5):
        db.add(TelemetryEvent(session_id=sess.id, event_type="dwell", dwell_seconds=random.uniform(*dwell_range)))

    compound = float(_analyzer.polarity_scores(sample_qa)["compound"])
    cls = classify_qa_feedback(sample_qa, compound)
    db.add(
        QAQuestion(
            session_id=sess.id,
            text=sample_qa,
            vader_compound=compound,
            sentiment_label=cls["sentiment_label"],
            feedback_type=cls["feedback_type"],
        )
    )
    db.commit()

    snapshot = compute_session_telemetry(db, sess)
    await ws_manager.broadcast(sess.code, {"type": "telemetry_update", "data": snapshot})
    return snapshot


@router.get("/api/v1/analytics/benchmarks")
def get_benchmarks():
    if not ml_engine.trained:
        ml_engine.train()
    return {
        "dataset_size": ml_engine.dataset_size,
        "benchmarks": ml_engine.benchmarks,
    }


@router.websocket("/ws/session/{code}")
async def websocket_session(websocket: WebSocket, code: str):
    await ws_manager.connect(code, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(code, websocket)
