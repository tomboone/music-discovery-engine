import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.clients.lastfm import LastfmClient
from app.config import Settings
from app.database import create_app_db, get_app_engine, get_app_session, get_mb_engine
from app.models.musicbrainz import reflect_mb_tables
from app.repositories.lastfm import LastfmRepository
from app.routers.lastfm import create_lastfm_router
from app.services.lastfm import LastfmService

SEED_USER_ID = uuid.UUID("d4e5f6a7-b8c9-4d0e-a1f2-b3c4d5e6f7a8")

settings = Settings()
app_engine: Engine | None = None
mb_engine: Engine | None = None


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

# Last.fm integration
lastfm_client = LastfmClient(
    api_key=settings.lastfm_api_key,
    shared_secret=settings.lastfm_shared_secret,
    callback_url=settings.lastfm_callback_url,
)
lastfm_repo = LastfmRepository()
lastfm_service = LastfmService(client=lastfm_client, repository=lastfm_repo)


def _get_app_session():
    assert app_engine is not None
    yield from get_app_session(app_engine)


app.include_router(
    create_lastfm_router(
        lastfm_service, lastfm_client, SEED_USER_ID, get_session=_get_app_session
    )
)


@app.get("/health")
async def health() -> dict:
    result = {"status": "ok", "databases": {}}

    try:
        assert app_engine is not None
        with app_engine.connect() as conn:
            conn.execute(text("SELECT 1")).scalar()
        result["databases"]["app"] = "ok"
    except Exception as e:
        result["status"] = "degraded"
        result["databases"]["app"] = str(e)

    try:
        assert mb_engine is not None
        with mb_engine.connect() as conn:
            conn.execute(text("SELECT 1")).scalar()
        result["databases"]["musicbrainz"] = "ok"
    except Exception as e:
        result["status"] = "degraded"
        result["databases"]["musicbrainz"] = str(e)

    return result
