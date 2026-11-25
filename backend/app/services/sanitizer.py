"""DPDP Act 2023 compliant text sanitization for anonymous Q&A and feedback."""
import re

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3,5}\)?[\s.-]?)?\d{3,5}[\s.-]?\d{4}\b")
_WHITESPACE_RE = re.compile(r"\s+")


def sanitize_text(text: str) -> str:
    """Strip HTML tags and URLs, mask emails and phone numbers as [REDACTED]."""
    if not text:
        return ""
    cleaned = _HTML_TAG_RE.sub(" ", str(text))
    cleaned = _URL_RE.sub(" ", cleaned)
    cleaned = _EMAIL_RE.sub("[REDACTED]", cleaned)
    cleaned = _PHONE_RE.sub("[REDACTED]", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    return cleaned


def classify_qa_feedback(text: str, vader_compound: float) -> dict:
    """Classify Q&A text into sentiment_label, feedback_type, and a plain-English nlp_explanation."""
    if vader_compound >= 0.05:
        sentiment_label = "Positive"
    elif vader_compound <= -0.05:
        sentiment_label = "Negative"
    else:
        sentiment_label = "Neutral"

    lower = (text or "").lower()

    if "?" in lower or any(
        kw in lower
        for kw in ("how ", "why ", "what ", "when ", "where ", "which ", "confused", "clarify", "explain", "can you", "could you")
    ):
        feedback_type = "Question & Clarification"
        reason = "question or clarification phrasing detected"
    elif any(
        kw in lower
        for kw in ("should ", "suggest", "improve", "better", "recommend", "too fast", "too slow", "more examples", "would be nice")
    ):
        feedback_type = "Improvement Suggestion"
        reason = "improvement or pacing suggestion keywords detected"
    elif any(kw in lower for kw in ("help", "stuck", "error", "issue", "problem", "broken", "not working", "can't", "cannot", "unable")):
        feedback_type = "Support Request"
        reason = "support or troubleshooting keywords detected"
    elif any(
        kw in lower
        for kw in ("api", "model", "latency", "shap", "catboost", "xgboost", "vader", "database", "sqlite", "websocket", "architecture", "benchmark")
    ):
        feedback_type = "Technical Feedback"
        reason = "technical architecture or ML keywords detected"
    elif sentiment_label == "Positive" or any(kw in lower for kw in ("great", "awesome", "love", "clear", "helpful", "amazing", "thanks", "thank you")):
        feedback_type = "Positive Praise"
        reason = "positive sentiment or praise keywords detected"
    else:
        feedback_type = "General Feedback"
        reason = "general audience comment"

    nlp_explanation = f"VADER {vader_compound:+.3f} ({sentiment_label}); {reason}."
    return {
        "sentiment_label": sentiment_label,
        "feedback_type": feedback_type,
        "nlp_explanation": nlp_explanation,
    }
