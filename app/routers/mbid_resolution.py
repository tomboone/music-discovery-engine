import contextlib
import uuid
from collections.abc import Callable, Generator

from fastapi import APIRouter
from sqlalchemy.orm import Session

from app.services.mbid_resolution import MbidResolutionService


def create_mbid_resolution_router(
    service: MbidResolutionService,
    seed_user_id: uuid.UUID,
    get_app_session: Callable[[], Generator[Session]],
    get_mb_session: Callable[[], Generator[Session]],
) -> APIRouter:
    router = APIRouter()

    @router.post("/mbid-resolution/run")
    async def run():
        app_gen = get_app_session()
        mb_gen = get_mb_session()
        app_session = next(app_gen)
        mb_session = next(mb_gen)
        try:
            return service.run(app_session, mb_session, seed_user_id)
        finally:
            with contextlib.suppress(StopIteration):
                next(app_gen)
            with contextlib.suppress(StopIteration):
                next(mb_gen)

    return router
