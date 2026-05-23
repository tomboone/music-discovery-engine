import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.generation import create_generation_router

SEED_USER_ID = uuid.UUID("d4e5f6a7-b8c9-4d0e-a1f2-b3c4d5e6f7a8")


@pytest.fixture
def mock_service():
    return MagicMock()


@pytest.fixture
def mock_mb_session():
    return MagicMock()


@pytest.fixture
def mock_app_session():
    return MagicMock()


@pytest.fixture
def app(mock_service, mock_mb_session, mock_app_session):
    app = FastAPI()

    def get_app_session_override():
        yield mock_app_session

    def get_mb_session_override():
        yield mock_mb_session

    router = create_generation_router(
        mock_service,
        SEED_USER_ID,
        get_app_session=get_app_session_override,
        get_mb_session=get_mb_session_override,
    )
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestGenerate:
    def test_successful_generation(self, client, mock_service):
        mock_service.generate.return_value = {
            "primary": {
                "artist": {"name": "Josh Rouse", "mbid": "aaa"},
                "seed_artist": {"name": "Yo La Tengo", "mbid": "bbb"},
                "source": "graph",
            },
            "also_explore": [
                {
                    "artist": {"name": "Lali Puna", "mbid": "ccc"},
                    "seed_artist": {"name": "The Notwist", "mbid": "ddd"},
                    "source": "lastfm_similar",
                }
            ],
            "metadata": {
                "seeds_used": [{"name": "Yo La Tengo", "mbid": "bbb"}],
                "total_candidates": 10,
                "filtered_by_history": 2,
                "generated_at": "2026-04-12T20:00:00+00:00",
            },
        }
        response = client.post("/recommendations/generate")
        assert response.status_code == 200
        data = response.json()
        assert data["primary"]["artist"]["name"] == "Josh Rouse"
        assert len(data["also_explore"]) == 1

    def test_custom_params(self, client, mock_service):
        mock_service.generate.return_value = {
            "primary": None,
            "also_explore": [],
            "metadata": {
                "seeds_used": [],
                "total_candidates": 0,
                "filtered_by_history": 0,
                "generated_at": "2026-04-12T20:00:00+00:00",
            },
        }
        response = client.post(
            "/recommendations/generate?num_seeds=3&num_also_explore=2"
        )
        assert response.status_code == 200
        call_kwargs = mock_service.generate.call_args.kwargs
        assert call_kwargs["num_seeds"] == 3
        assert call_kwargs["num_also_explore"] == 2

    def test_no_taste_profile_returns_400(self, client, mock_service):
        mock_service.generate.return_value = {"error": "no_taste_profile"}
        response = client.post("/recommendations/generate")
        assert response.status_code == 400
        assert response.json()["error"] == "no_taste_profile"

    def test_no_seedable_artists_returns_400(self, client, mock_service):
        mock_service.generate.return_value = {"error": "no_seedable_artists"}
        response = client.post("/recommendations/generate")
        assert response.status_code == 400
