import contextlib
import uuid
from collections.abc import Callable, Generator

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.services.generation import GenerationService


def create_generation_router(
    service: GenerationService,
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

    @router.post("/recommendations/generate")
    async def generate(
        num_seeds: int = Query(default=5, ge=1, le=20),
        num_also_explore: int = Query(default=4, ge=0, le=10),
    ):
        app_gen = _get_app_session()
        mb_gen = _get_mb_session()
        app_session = next(app_gen)
        mb_session = next(mb_gen)
        try:
            result = service.generate(
                mb_session=mb_session,
                app_session=app_session,
                user_id=seed_user_id,
                num_seeds=num_seeds,
                num_also_explore=num_also_explore,
            )
            if "error" in result:
                return JSONResponse(
                    status_code=400,
                    content=result,
                )
            return result
        finally:
            with contextlib.suppress(StopIteration):
                next(app_gen)
            with contextlib.suppress(StopIteration):
                next(mb_gen)

    return router
