"""SQLite + SQLAlchemy database configuration."""
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "eventpulse.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Safely add new QA columns to existing SQLite databases if missing."""
    with engine.begin() as conn:
        for ddl in (
            "ALTER TABLE qa_questions ADD COLUMN sentiment_label VARCHAR(32) DEFAULT 'Neutral'",
            "ALTER TABLE qa_questions ADD COLUMN feedback_type VARCHAR(64) DEFAULT 'General Feedback'",
            "ALTER TABLE poll_votes ADD COLUMN voter_token VARCHAR(128)",
        ):
            try:
                conn.execute(text(ddl))
            except Exception:
                pass


init_db()
