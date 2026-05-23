import contextlib
import uuid
from collections.abc import Callable, Generator

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.clients.lastfm import LastfmApiError, LastfmAuthError, LastfmClient
from app.services.lastfm import LastfmService


def create_lastfm_router(
    service: LastfmService,
    client: LastfmClient,
    seed_user_id: uuid.UUID,
    get_session: Callable[[], Generator[Session]] | None = None,
) -> APIRouter:
    router = APIRouter()

    def _get_session() -> Generator[Session]:
        if get_session:
            yield from get_session()
        else:
            from app.config import Settings
            from app.database import get_app_engine, get_app_session

            settings = Settings()
            engine = get_app_engine(settings)
            yield from get_app_session(engine)

    @router.get("/auth/lastfm")
    async def auth_redirect():
        url = client.get_auth_url()
        return RedirectResponse(url=url)

    @router.get("/auth/lastfm/callback")
    async def auth_callback(token: str = Query(...)):
        gen = _get_session()
        session = next(gen)
        try:
            profile = service.complete_auth(session, seed_user_id, token)
            return {"status": "linked", "username": profile.lastfm_username}
        except LastfmAuthError as e:
            return JSONResponse(status_code=401, content={"error": str(e)})
        finally:
            with contextlib.suppress(StopIteration):
                next(gen)

    @router.post("/lastfm/sync")
    async def sync():
        gen = _get_session()
        session = next(gen)
        try:
            result = service.sync_taste_profile(session, seed_user_id)
            return result
        except ValueError as e:
            return JSONResponse(status_code=400, content={"error": str(e)})
        except LastfmApiError as e:
            return JSONResponse(status_code=502, content={"error": str(e)})
        finally:
            with contextlib.suppress(StopIteration):
                next(gen)

    @router.get("/lastfm/status")
    async def status():
        gen = _get_session()
        session = next(gen)
        try:
            repo = service._repository
            profile = repo.get_lastfm_profile(session, seed_user_id)
            if profile:
                return {
                    "linked": True,
                    "username": profile.lastfm_username,
                    "last_synced_at": (
                        profile.last_synced_at.isoformat()
                        if profile.last_synced_at
                        else None
                    ),
                }
            return {"linked": False}
        finally:
            with contextlib.suppress(StopIteration):
                next(gen)

    return router
