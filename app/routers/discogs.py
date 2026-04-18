import contextlib
import uuid
from collections.abc import Callable, Generator

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.clients.discogs import DiscogsApiError, DiscogsAuthError
from app.services.discogs import DiscogsService


def create_discogs_router(
    service: DiscogsService,
    seed_user_id: uuid.UUID,
    get_session: Callable[[], Generator[Session]],
) -> APIRouter:
    router = APIRouter()

    @router.get("/auth/discogs")
    async def auth_redirect():
        gen = get_session()
        session = next(gen)
        try:
            url = service.begin_auth(session, seed_user_id)
            return RedirectResponse(url=url)
        finally:
            with contextlib.suppress(StopIteration):
                next(gen)

    @router.get("/auth/discogs/callback")
    async def auth_callback(
        oauth_token: str = Query(...), oauth_verifier: str = Query(...)
    ):
        gen = get_session()
        session = next(gen)
        try:
            profile = service.complete_auth(session, oauth_token, oauth_verifier)
            return {"status": "linked", "username": profile.discogs_username}
        except ValueError as e:
            return JSONResponse(status_code=400, content={"error": str(e)})
        except DiscogsAuthError as e:
            return JSONResponse(status_code=401, content={"error": str(e)})
        finally:
            with contextlib.suppress(StopIteration):
                next(gen)

    @router.post("/discogs/sync")
    async def sync():
        gen = get_session()
        session = next(gen)
        try:
            return service.sync_taste_profile(session, seed_user_id)
        except ValueError as e:
            return JSONResponse(status_code=400, content={"error": str(e)})
        except DiscogsApiError as e:
            if e.status == 401:
                return JSONResponse(
                    status_code=401,
                    content={"error": "re-authentication required"},
                )
            if e.status == 429:
                return JSONResponse(status_code=503, content={"error": str(e)})
            return JSONResponse(status_code=502, content={"error": str(e)})
        finally:
            with contextlib.suppress(StopIteration):
                next(gen)

    @router.get("/discogs/status")
    async def status():
        gen = get_session()
        session = next(gen)
        try:
            return service.get_status(session, seed_user_id)
        finally:
            with contextlib.suppress(StopIteration):
                next(gen)

    return router
