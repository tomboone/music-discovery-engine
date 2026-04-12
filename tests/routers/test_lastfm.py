import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.clients.lastfm import LastfmApiError, LastfmAuthError
from app.models.app import LastfmProfile
from app.routers.lastfm import create_lastfm_router

SEED_USER_ID = uuid.UUID("d4e5f6a7-b8c9-4d0e-a1f2-b3c4d5e6f7a8")


@pytest.fixture
def mock_service():
    return MagicMock()


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def app(mock_service, mock_client, mock_session):
    app = FastAPI()

    def get_session_override():
        yield mock_session

    router = create_lastfm_router(
        mock_service, mock_client, SEED_USER_ID, get_session=get_session_override
    )
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestAuthRedirect:
    def test_redirects_to_lastfm(self, client, mock_client):
        mock_client.get_auth_url.return_value = "https://www.last.fm/api/auth/?api_key=test"
        response = client.get("/auth/lastfm", follow_redirects=False)
        assert response.status_code == 307
        assert "last.fm" in response.headers["location"]


class TestAuthCallback:
    def test_successful_callback(self, client, mock_service):
        mock_service.complete_auth.return_value = LastfmProfile(
            id=uuid.uuid4(),
            user_id=SEED_USER_ID,
            lastfm_username="testuser",
            session_key="key123",
        )
        response = client.get("/auth/lastfm/callback?token=valid_token")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["status"] == "linked"

    def test_auth_error_returns_401(self, client, mock_service):
        mock_service.complete_auth.side_effect = LastfmAuthError("bad token")
        response = client.get("/auth/lastfm/callback?token=bad")
        assert response.status_code == 401

    def test_missing_token_returns_422(self, client):
        response = client.get("/auth/lastfm/callback")
        assert response.status_code == 422


class TestSync:
    def test_successful_sync(self, client, mock_service):
        mock_service.sync_taste_profile.return_value = {
            "artists_count": 100,
            "albums_count": 200,
            "synced_at": "2026-04-12T00:00:00+00:00",
        }
        response = client.post("/lastfm/sync")
        assert response.status_code == 200
        data = response.json()
        assert data["artists_count"] == 100
        assert data["albums_count"] == 200

    def test_sync_without_profile_returns_400(self, client, mock_service):
        mock_service.sync_taste_profile.side_effect = ValueError("Last.fm account not linked")
        response = client.post("/lastfm/sync")
        assert response.status_code == 400

    def test_sync_api_error_returns_502(self, client, mock_service):
        mock_service.sync_taste_profile.side_effect = LastfmApiError("API down")
        response = client.post("/lastfm/sync")
        assert response.status_code == 502


class TestStatus:
    def test_status_when_linked(self, client, mock_service):
        profile = LastfmProfile(
            id=uuid.uuid4(),
            user_id=SEED_USER_ID,
            lastfm_username="testuser",
            session_key="key",
            last_synced_at=None,
        )
        mock_service._repository.get_lastfm_profile.return_value = profile
        response = client.get("/lastfm/status")
        assert response.status_code == 200
        data = response.json()
        assert data["linked"] is True
        assert data["username"] == "testuser"

    def test_status_when_not_linked(self, client, mock_service):
        mock_service._repository.get_lastfm_profile.return_value = None
        response = client.get("/lastfm/status")
        assert response.status_code == 200
        data = response.json()
        assert data["linked"] is False
