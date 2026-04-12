import uuid
from unittest.mock import MagicMock

import pytest

from app.services.recommendations import RecommendationService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo):
    return RecommendationService(repository=mock_repo)


SEED_MBID = uuid.UUID("00000000-0000-0000-0000-000000000001")
KNOWN_MBID = uuid.UUID("00000000-0000-0000-0000-000000000100")
UNKNOWN_MBID = uuid.UUID("00000000-0000-0000-0000-000000000200")
USER_ID = uuid.UUID("d4e5f6a7-b8c9-4d0e-a1f2-b3c4d5e6f7a8")


class TestGetRecommendations:
    def test_filters_known_artists(self, service, mock_repo):
        mock_repo.get_artist_by_mbid.return_value = {
            "name": "Seed Artist",
            "mbid": str(SEED_MBID),
        }
        mock_repo.find_multi_path_artists.return_value = [
            {
                "artist_name": "Known Artist",
                "artist_mbid": str(KNOWN_MBID),
                "path_count": 3,
                "paths": [{"relationship_type": "producer", "via": "P1"}],
            },
            {
                "artist_name": "Unknown Artist",
                "artist_mbid": str(UNKNOWN_MBID),
                "path_count": 2,
                "paths": [{"relationship_type": "performer", "via": "P2"}],
            },
        ]

        mock_mb_session = MagicMock()
        mock_app_session = MagicMock()
        mock_app_session.execute.return_value.scalars.return_value.all.return_value = [
            KNOWN_MBID,
        ]

        result = service.get_recommendations(
            mb_session=mock_mb_session,
            app_session=mock_app_session,
            seed_mbid=SEED_MBID,
            user_id=USER_ID,
        )

        assert len(result["recommendations"]) == 1
        assert result["recommendations"][0]["artist"]["name"] == "Unknown Artist"
        assert result["filtered_known_artists"] == 1

    def test_seed_not_found_returns_none(self, service, mock_repo):
        mock_repo.get_artist_by_mbid.return_value = None
        mock_mb_session = MagicMock()
        mock_app_session = MagicMock()

        result = service.get_recommendations(
            mb_session=mock_mb_session,
            app_session=mock_app_session,
            seed_mbid=SEED_MBID,
            user_id=USER_ID,
        )

        assert result is None

    def test_empty_results(self, service, mock_repo):
        mock_repo.get_artist_by_mbid.return_value = {
            "name": "Seed Artist",
            "mbid": str(SEED_MBID),
        }
        mock_repo.find_multi_path_artists.return_value = []
        mock_mb_session = MagicMock()
        mock_app_session = MagicMock()
        mock_app_session.execute.return_value.scalars.return_value.all.return_value = []

        result = service.get_recommendations(
            mb_session=mock_mb_session,
            app_session=mock_app_session,
            seed_mbid=SEED_MBID,
            user_id=USER_ID,
        )

        assert result["recommendations"] == []
        assert result["filtered_known_artists"] == 0

    def test_includes_params_in_response(self, service, mock_repo):
        mock_repo.get_artist_by_mbid.return_value = {
            "name": "Seed Artist",
            "mbid": str(SEED_MBID),
        }
        mock_repo.find_multi_path_artists.return_value = []
        mock_mb_session = MagicMock()
        mock_app_session = MagicMock()
        mock_app_session.execute.return_value.scalars.return_value.all.return_value = []

        result = service.get_recommendations(
            mb_session=mock_mb_session,
            app_session=mock_app_session,
            seed_mbid=SEED_MBID,
            user_id=USER_ID,
            relationship_types=["producer", "vocal"],
            min_paths=3,
            limit=10,
        )

        assert result["params"]["relationship_types"] == ["producer", "vocal"]
        assert result["params"]["min_paths"] == 3
        assert result["params"]["limit"] == 10

    def test_includes_seed_artist_in_response(self, service, mock_repo):
        mock_repo.get_artist_by_mbid.return_value = {
            "name": "Yo La Tengo",
            "mbid": str(SEED_MBID),
        }
        mock_repo.find_multi_path_artists.return_value = []
        mock_mb_session = MagicMock()
        mock_app_session = MagicMock()
        mock_app_session.execute.return_value.scalars.return_value.all.return_value = []

        result = service.get_recommendations(
            mb_session=mock_mb_session,
            app_session=mock_app_session,
            seed_mbid=SEED_MBID,
            user_id=USER_ID,
        )

        assert result["seed_artist"]["name"] == "Yo La Tengo"
