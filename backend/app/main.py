"""EventPulse AI FastAPI application entrypoint."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import Base, engine, SessionLocal
from app.db.models import EventSession
from app.services.ml_engine import ml_engine
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(EventSession).filter(EventSession.code == "DEMO-101").first():
            db.add(EventSession(code="DEMO-101", title="EventPulse AI Live Cohort", is_active=True))
            db.commit()
    finally:
        db.close()

    if not ml_engine.trained:
        ml_engine.train()
    yield


app = FastAPI(title="EventPulse AI", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok", "ml_trained": ml_engine.trained}
