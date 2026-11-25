"""Pytest suite for EventPulse AI."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app
from app.services.sanitizer import sanitize_text
from app.services.dataset import build_cleaned_dataset, FEATURE_COLUMNS
from app.services.ml_engine import ml_engine, classify_risk_tier


def test_sanitizer_dpdp_compliance():
    raw = "<script>alert(1)</script>Reach me at alice@example.com or +91 9876543210 via https://evil.com"
    cleaned = sanitize_text(raw)
    assert "<script>" not in cleaned
    assert "https://evil.com" not in cleaned
    assert "alice@example.com" not in cleaned
    assert "9876543210" not in cleaned
    assert "[REDACTED]" in cleaned


def test_dataset_pipeline():
    df = build_cleaned_dataset()
    assert len(df) >= 1200
    for col in FEATURE_COLUMNS:
        assert col in df.columns
    assert "disengagement_target" in df.columns


def test_ml_engine_and_shap():
    if not ml_engine.trained:
        ml_engine.train()
    assert len(ml_engine.benchmarks) == 4
    res = ml_engine.predict_with_shap({
        "vader_compound": -0.6,
        "disengaged_ratio": 0.7,
        "confused_ratio": 0.2,
        "positive_ratio": 0.1,
        "avg_dwell_seconds": 25.0,
        "poll_participation_rate": 0.2,
    })
    assert 0.0 <= res["risk_probability"] <= 1.0
    assert res["risk_tier"] in {"Optimal", "Mild Drift", "Moderate Slump", "Severe Disengagement"}
    assert len(res["top_shap_attributions"]) > 0
    assert classify_risk_tier(0.1) == "Optimal"
    assert classify_risk_tier(0.85) == "Severe Disengagement"


def test_rest_endpoints_and_simulator():
    with TestClient(app) as client:
        r = client.get("/api/v1/sessions/active?code=DEMO-101")
        assert r.status_code == 200
        assert r.json()["session_code"] == "DEMO-101"

        r_sim = client.post("/api/v1/demo/simulate", json={"session_code": "DEMO-101", "mode": "confusion_spike"})
        assert r_sim.status_code == 200
        assert "prediction" in r_sim.json()

        r_qa = client.post("/api/v1/qa", json={"session_code": "DEMO-101", "text": "Email me at bob@test.org"})
        assert r_qa.status_code == 200
        qa_item = r_qa.json()["qa"][0]
        assert "[REDACTED]" in qa_item["text"]
        assert qa_item["sentiment_label"] in ("Positive", "Neutral", "Negative")
        assert qa_item["feedback_type"] in (
            "Question & Clarification",
            "Improvement Suggestion",
            "Support Request",
            "Technical Feedback",
            "Positive Praise",
            "General Feedback",
        )
        assert isinstance(qa_item["nlp_explanation"], str) and len(qa_item["nlp_explanation"]) > 0

        r_bench = client.get("/api/v1/analytics/benchmarks")
        assert r_bench.status_code == 200
        assert len(r_bench.json()["benchmarks"]) == 4


def test_poll_one_vote_per_attendee():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        r_poll = client.post(
            "/api/v1/polls",
            json={
                "session_code": "DEMO-101",
                "question": "Rate the pace",
                "options": ["Good", "Too fast"],
            },
        )
        assert r_poll.status_code == 200
        poll_id = r_poll.json()["polls"][0]["id"]

        r_v1 = client.post(
            f"/api/v1/polls/{poll_id}/vote",
            json={"option_index": 0, "voter_token": "tok-alpha"},
        )
        assert r_v1.status_code == 200

        r_dup = client.post(
            f"/api/v1/polls/{poll_id}/vote",
            json={"option_index": 1, "voter_token": "tok-alpha"},
        )
        assert r_dup.status_code == 409

        r_v2 = client.post(
            f"/api/v1/polls/{poll_id}/vote",
            json={"option_index": 1, "voter_token": "tok-beta"},
        )
        assert r_v2.status_code == 200
