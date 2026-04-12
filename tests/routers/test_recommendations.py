import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.recommendations import create_recommendations_router

SEED_USER_ID = uuid.UUID("d4e5f6a7-b8c9-4d0e-a1f2-b3c4d5e6f7a8")
SEED_MBID = "3f542031-b054-454d-b57b-812fa2a81b11"


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

    router = create_recommendations_router(
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


class TestGetRecommendations:
    def test_successful_response(self, client, mock_service):
        mock_service.get_recommendations.return_value = {
            "seed_artist": {"name": "Yo La Tengo", "mbid": SEED_MBID},
            "recommendations": [
                {
                    "artist": {"name": "Amy Rigby", "mbid": "aaa"},
                    "path_count": 2,
                    "paths": [
                        {"relationship_type": "producer", "via": "Roger Moutenot"},
                    ],
                }
            ],
            "params": {
                "relationship_types": [
                    "producer",
                    "instrument",
                    "performer",
                    "vocal",
                ],
                "min_paths": 2,
                "limit": 20,
            },
            "filtered_known_artists": 3,
        }
        response = client.get(f"/recommendations?seed_mbid={SEED_MBID}")
        assert response.status_code == 200
        data = response.json()
        assert data["seed_artist"]["name"] == "Yo La Tengo"
        assert len(data["recommendations"]) == 1
        assert data["filtered_known_artists"] == 3

    def test_custom_params(self, client, mock_service):
        mock_service.get_recommendations.return_value = {
            "seed_artist": {"name": "Test", "mbid": SEED_MBID},
            "recommendations": [],
            "params": {
                "relationship_types": ["producer"],
                "min_paths": 3,
                "limit": 5,
            },
            "filtered_known_artists": 0,
        }
        response = client.get(
            f"/recommendations?seed_mbid={SEED_MBID}"
            "&relationship_types=producer&min_paths=3&limit=5"
        )
        assert response.status_code == 200
        call_kwargs = mock_service.get_recommendations.call_args
        assert call_kwargs.kwargs["relationship_types"] == ["producer"]
        assert call_kwargs.kwargs["min_paths"] == 3
        assert call_kwargs.kwargs["limit"] == 5

    def test_seed_not_found_returns_404(self, client, mock_service):
        mock_service.get_recommendations.return_value = None
        response = client.get(f"/recommendations?seed_mbid={SEED_MBID}")
        assert response.status_code == 404

    def test_missing_seed_mbid_returns_422(self, client):
        response = client.get("/recommendations")
        assert response.status_code == 422

    def test_invalid_uuid_returns_422(self, client):
        response = client.get("/recommendations?seed_mbid=not-a-uuid")
        assert response.status_code == 422

    def test_weight_params(self, client, mock_service):
        mock_service.get_recommendations.return_value = {
            "seed_artist": {"name": "Test", "mbid": SEED_MBID},
            "recommendations": [],
            "params": {
                "relationship_types": ["producer", "instrument", "performer", "vocal"],
                "min_paths": 2,
                "limit": 20,
                "weights": {
                    "path_count": 2.0,
                    "genre_affinity": 1.0,
                    "collaborator_diversity": 0.0,
                },
            },
            "filtered_known_artists": 0,
        }
        response = client.get(
            f"/recommendations?seed_mbid={SEED_MBID}"
            "&weight_path_count=2.0"
            "&weight_genre_affinity=1.0"
            "&weight_collaborator_diversity=0.0"
        )
        assert response.status_code == 200
        call_kwargs = mock_service.get_recommendations.call_args
        assert call_kwargs.kwargs["weights"]["path_count"] == 2.0
        assert call_kwargs.kwargs["weights"]["genre_affinity"] == 1.0
        assert call_kwargs.kwargs["weights"]["collaborator_diversity"] == 0.0

    def test_score_in_response(self, client, mock_service):
        mock_service.get_recommendations.return_value = {
            "seed_artist": {"name": "Test", "mbid": SEED_MBID},
            "recommendations": [
                {
                    "artist": {"name": "Rec", "mbid": "aaa"},
                    "path_count": 2,
                    "paths": [],
                    "score": {
                        "path_count": 2,
                        "genre_affinity": 0.5,
                        "collaborator_diversity": 0.3,
                        "final_score": 2.84,
                    },
                }
            ],
            "params": {
                "relationship_types": ["producer"],
                "min_paths": 2,
                "limit": 20,
                "weights": {
                    "path_count": 1.0,
                    "genre_affinity": 0.5,
                    "collaborator_diversity": 0.3,
                },
            },
            "filtered_known_artists": 0,
        }
        response = client.get(f"/recommendations?seed_mbid={SEED_MBID}")
        data = response.json()
        rec = data["recommendations"][0]
        assert "score" in rec
        assert rec["score"]["final_score"] == 2.84

    def test_min_graph_results_param(self, client, mock_service):
        mock_service.get_recommendations.return_value = {
            "seed_artist": {"name": "Test", "mbid": SEED_MBID},
            "recommendations": [],
            "fallback_recommendations": [
                {
                    "artist": {"name": "Similar", "mbid": ""},
                    "match": 0.8,
                    "source": "lastfm_similar",
                }
            ],
            "fallback_reason": "graph_results_below_threshold",
            "params": {
                "relationship_types": ["producer"],
                "min_paths": 2,
                "limit": 20,
                "weights": {
                    "path_count": 1.0,
                    "genre_affinity": 0.5,
                    "collaborator_diversity": 0.3,
                },
                "min_graph_results": 10,
            },
            "filtered_known_artists": 0,
        }
        response = client.get(
            f"/recommendations?seed_mbid={SEED_MBID}&min_graph_results=10"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["fallback_recommendations"]) == 1
        assert data["fallback_reason"] == "graph_results_below_threshold"
        call_kwargs = mock_service.get_recommendations.call_args
        assert call_kwargs.kwargs["min_graph_results"] == 10
