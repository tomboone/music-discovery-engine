import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.clients.discogs import DiscogsClient
from app.clients.lastfm import LastfmClient
from app.config import Settings
from app.database import (
    create_app_db,
    get_app_engine,
    get_app_session,
    get_mb_engine,
    get_mb_session,
)
from app.models.musicbrainz import reflect_mb_tables
from app.repositories.discogs import DiscogsRepository
from app.repositories.generation import GenerationRepository
from app.repositories.lastfm import LastfmRepository
from app.repositories.mbid_resolution import MbidResolutionRepository
from app.repositories.recommendations import RecommendationRepository
from app.routers.discogs import create_discogs_router
from app.routers.generation import create_generation_router
from app.routers.lastfm import create_lastfm_router
from app.routers.mbid_resolution import create_mbid_resolution_router
from app.routers.recommendations import create_recommendations_router
from app.services.discogs import DiscogsService
from app.services.generation import GenerationService
from app.services.lastfm import LastfmService
from app.services.mbid_resolution import MbidResolutionService
from app.services.recommendations import RecommendationService
from app.services.taste_profile.ingester import TasteProfileIngester

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
taste_profile_ingester = TasteProfileIngester()
lastfm_service = LastfmService(
    client=lastfm_client, repository=lastfm_repo, ingester=taste_profile_ingester
)


def _get_app_session():
    assert app_engine is not None
    yield from get_app_session(app_engine)


app.include_router(
    create_lastfm_router(
        lastfm_service, lastfm_client, SEED_USER_ID, get_session=_get_app_session
    )
)

# Discogs integration
discogs_client = DiscogsClient(
    consumer_key=settings.discogs_consumer_key,
    consumer_secret=settings.discogs_consumer_secret,
    callback_url=settings.discogs_callback_url,
    user_agent=settings.discogs_user_agent,
)
discogs_repo = DiscogsRepository()
discogs_service = DiscogsService(
    client=discogs_client,
    repository=discogs_repo,
    ingester=taste_profile_ingester,
)
app.include_router(
    create_discogs_router(discogs_service, SEED_USER_ID, _get_app_session)
)

# Recommendations
rec_repo = RecommendationRepository()
rec_service = RecommendationService(repository=rec_repo, lastfm_client=lastfm_client)


def _get_mb_session():
    assert mb_engine is not None
    yield from get_mb_session(mb_engine)


app.include_router(
    create_recommendations_router(
        rec_service,
        SEED_USER_ID,
        get_app_session=_get_app_session,
        get_mb_session=_get_mb_session,
    )
)

# MBID resolution
mbid_resolution_repo = MbidResolutionRepository()
mbid_resolution_service = MbidResolutionService(repository=mbid_resolution_repo)
app.include_router(
    create_mbid_resolution_router(
        mbid_resolution_service,
        SEED_USER_ID,
        get_app_session=_get_app_session,
        get_mb_session=_get_mb_session,
    )
)

# Generation
gen_repo = GenerationRepository()
gen_service = GenerationService(
    recommendation_service=rec_service,
    repository=gen_repo,
)

app.include_router(
    create_generation_router(
        gen_service,
        SEED_USER_ID,
        get_app_session=_get_app_session,
        get_mb_session=_get_mb_session,
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
