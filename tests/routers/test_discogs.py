import uuid
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.clients.discogs import DiscogsAuthError
from app.models.app import Base, User
from app.routers.discogs import create_discogs_router

SEED_USER_ID = uuid.UUID("d4e5f6a7-b8c9-4d0e-a1f2-b3c4d5e6f7a8")


def _make_app_and_mocks():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    def _get_session():
        with Session(engine) as s:
            yield s

    with Session(engine) as s:
        s.add(User(id=SEED_USER_ID, email="t@example.com"))
        s.commit()

    mock_service = MagicMock()
    app = FastAPI()
    app.include_router(create_discogs_router(mock_service, SEED_USER_ID, _get_session))
    return TestClient(app), mock_service


def test_auth_redirect_returns_redirect():
    client, service = _make_app_and_mocks()
    service.begin_auth.return_value = (
        "https://www.discogs.com/oauth/authorize?oauth_token=rt"
    )
    r = client.get("/auth/discogs", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"].startswith("https://www.discogs.com/oauth/authorize")


def test_callback_happy_path():
    client, service = _make_app_and_mocks()
    service.complete_auth.return_value = MagicMock(
        discogs_username="audiophilesasquatch"
    )
    r = client.get("/auth/discogs/callback?oauth_token=rt&oauth_verifier=v")
    assert r.status_code == 200
    assert r.json() == {"status": "linked", "username": "audiophilesasquatch"}


def test_callback_unknown_token_returns_400():
    client, service = _make_app_and_mocks()
    service.complete_auth.side_effect = ValueError("unknown oauth_token")
    r = client.get("/auth/discogs/callback?oauth_token=nope&oauth_verifier=v")
    assert r.status_code == 400
    assert "unknown" in r.json()["error"]


def test_callback_auth_error_returns_401():
    client, service = _make_app_and_mocks()
    service.complete_auth.side_effect = DiscogsAuthError("bad verifier")
    r = client.get("/auth/discogs/callback?oauth_token=rt&oauth_verifier=bad")
    assert r.status_code == 401


def test_sync_happy_path():
    client, service = _make_app_and_mocks()
    service.sync_taste_profile.return_value = {
        "artists_count": 5,
        "albums_count": 3,
        "synced_at": "2026-04-18T00:00:00+00:00",
    }
    r = client.post("/discogs/sync")
    assert r.status_code == 200
    assert r.json()["artists_count"] == 5


def test_sync_unlinked_returns_400():
    client, service = _make_app_and_mocks()
    service.sync_taste_profile.side_effect = ValueError("Discogs account not linked")
    r = client.post("/discogs/sync")
    assert r.status_code == 400


def test_sync_401_returns_401():
    from app.clients.discogs import DiscogsApiError

    client, service = _make_app_and_mocks()
    service.sync_taste_profile.side_effect = DiscogsApiError(401, "unauthorized")
    r = client.post("/discogs/sync")
    assert r.status_code == 401


def test_sync_5xx_returns_502():
    from app.clients.discogs import DiscogsApiError

    client, service = _make_app_and_mocks()
    service.sync_taste_profile.side_effect = DiscogsApiError(503, "service unavailable")
    r = client.post("/discogs/sync")
    assert r.status_code == 502


def test_status_unlinked():
    client, service = _make_app_and_mocks()
    service.get_status.return_value = {"linked": False}
    r = client.get("/discogs/status")
    assert r.status_code == 200
    assert r.json() == {"linked": False}


def test_status_linked():
    client, service = _make_app_and_mocks()
    service.get_status.return_value = {
        "linked": True,
        "username": "audiophilesasquatch",
        "last_synced_at": "2026-04-18T00:00:00+00:00",
    }
    r = client.get("/discogs/status")
    body = r.json()
    assert body["linked"] is True
    assert body["username"] == "audiophilesasquatch"
    assert body["last_synced_at"].startswith("2026-04-18")
