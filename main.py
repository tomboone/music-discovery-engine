from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.config import Settings
from app.database import create_app_db, get_app_engine, get_mb_engine
from app.models.musicbrainz import reflect_mb_tables

settings = Settings()
app_engine = None
mb_engine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global app_engine, mb_engine
    create_app_db(settings)
    app_engine = get_app_engine(settings)
    mb_engine = get_mb_engine(settings)
    reflect_mb_tables(mb_engine)
    yield
    if app_engine:
        app_engine.dispose()
    if mb_engine:
        mb_engine.dispose()


app = FastAPI(title="Music Discovery Engine", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    result = {"status": "ok", "databases": {}}

    try:
        with app_engine.connect() as conn:
            conn.execute(text("SELECT 1")).scalar()
        result["databases"]["app"] = "ok"
    except Exception as e:
        result["status"] = "degraded"
        result["databases"]["app"] = str(e)

    try:
        with mb_engine.connect() as conn:
            conn.execute(text("SELECT 1")).scalar()
        result["databases"]["musicbrainz"] = "ok"
    except Exception as e:
        result["status"] = "degraded"
        result["databases"]["musicbrainz"] = str(e)

    return result
