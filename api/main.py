import logging

from fastapi import FastAPI
from sqlalchemy import text

from api.routes import clips, jobs, videos
from models.db import engine

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="YouTube Clip + Persian Dub Platform")

app.include_router(videos.router)
app.include_router(clips.router)
app.include_router(jobs.router)


@app.get("/health")
def health():
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {"status": "ok", "database": "ok" if db_ok else "unreachable"}
