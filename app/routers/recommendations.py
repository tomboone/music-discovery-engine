import contextlib
import uuid
from collections.abc import Callable, Generator

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.services.recommendations import RecommendationService

DEFAULT_TYPES = "producer,instrument,performer,vocal"


def create_recommendations_router(
    service: RecommendationService,
    seed_user_id: uuid.UUID,
    get_app_session: Callable[[], Generator[Session]] | None = None,
    get_mb_session: Callable[[], Generator[Session]] | None = None,
) -> APIRouter:
    router = APIRouter()

    def _get_app_session() -> Generator[Session]:
        if get_app_session:
            yield from get_app_session()
        else:
            from app.config import Settings
            from app.database import get_app_engine
            from app.database import get_app_session as _gas

            settings = Settings()
            engine = get_app_engine(settings)
            yield from _gas(engine)

    def _get_mb_session() -> Generator[Session]:
        if get_mb_session:
            yield from get_mb_session()
        else:
            from app.config import Settings
            from app.database import get_mb_engine
            from app.database import get_mb_session as _gms

            settings = Settings()
            engine = get_mb_engine(settings)
            yield from _gms(engine)

    @router.get("/recommendations")
    async def get_recommendations(
        seed_mbid: uuid.UUID = Query(...),
        relationship_types: str = Query(default=DEFAULT_TYPES),
        min_paths: int = Query(default=2, ge=1),
        limit: int = Query(default=20, ge=1, le=100),
        weight_path_count: float = Query(default=1.0, ge=0.0),
        weight_genre_affinity: float = Query(default=0.5, ge=0.0),
        weight_collaborator_diversity: float = Query(default=0.3, ge=0.0),
    ):
        types_list = [t.strip() for t in relationship_types.split(",") if t.strip()]
        weights = {
            "path_count": weight_path_count,
            "genre_affinity": weight_genre_affinity,
            "collaborator_diversity": weight_collaborator_diversity,
        }

        app_gen = _get_app_session()
        mb_gen = _get_mb_session()
        app_session = next(app_gen)
        mb_session = next(mb_gen)
        try:
            result = service.get_recommendations(
                mb_session=mb_session,
                app_session=app_session,
                seed_mbid=seed_mbid,
                user_id=seed_user_id,
                relationship_types=types_list,
                min_paths=min_paths,
                limit=limit,
                weights=weights,
            )
            if result is None:
                return JSONResponse(
                    status_code=404,
                    content={"error": "Seed artist not found"},
                )
            return result
        finally:
            with contextlib.suppress(StopIteration):
                next(app_gen)
            with contextlib.suppress(StopIteration):
                next(mb_gen)

    return router
