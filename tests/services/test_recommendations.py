import uuid
from unittest.mock import MagicMock

import pytest

from app.services.recommendations import RecommendationService

SEED_MBID = uuid.UUID("00000000-0000-0000-0000-000000000001")
KNOWN_MBID = uuid.UUID("00000000-0000-0000-0000-000000000100")
UNKNOWN_MBID = uuid.UUID("00000000-0000-0000-0000-000000000200")
USER_ID = uuid.UUID("d4e5f6a7-b8c9-4d0e-a1f2-b3c4d5e6f7a8")


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_artist_tags.return_value = {}
    return repo


@pytest.fixture
def service(mock_repo):
    return RecommendationService(repository=mock_repo)


def _make_candidate(name, mbid, path_count=2, paths=None):
    if paths is None:
        paths = [
            {
                "relationship_type": "producer",
                "via": "P1",
                "collaborator_artist_count": 10,
            }
        ]
    return {
        "artist_name": name,
        "artist_mbid": str(mbid),
        "path_count": path_count,
        "paths": paths,
    }


class TestGetRecommendations:
    def test_filters_known_artists(self, service, mock_repo):
        mock_repo.get_artist_by_mbid.return_value = {
            "name": "Seed",
            "mbid": str(SEED_MBID),
        }
        mock_repo.find_multi_path_artists.return_value = [
            _make_candidate("Known", KNOWN_MBID),
            _make_candidate("Unknown", UNKNOWN_MBID),
        ]
        mock_mb = MagicMock()
        mock_app = MagicMock()
        mock_app.execute.return_value.scalars.return_value.all.return_value = [
            KNOWN_MBID,
        ]

        result = service.get_recommendations(
            mb_session=mock_mb,
            app_session=mock_app,
            seed_mbid=SEED_MBID,
            user_id=USER_ID,
        )

        assert len(result["recommendations"]) == 1
        assert result["recommendations"][0]["artist"]["name"] == "Unknown"
        assert result["filtered_known_artists"] == 1

    def test_seed_not_found_returns_none(self, service, mock_repo):
        mock_repo.get_artist_by_mbid.return_value = None
        result = service.get_recommendations(
            mb_session=MagicMock(),
            app_session=MagicMock(),
            seed_mbid=SEED_MBID,
            user_id=USER_ID,
        )
        assert result is None

    def test_empty_results(self, service, mock_repo):
        mock_repo.get_artist_by_mbid.return_value = {
            "name": "Seed",
            "mbid": str(SEED_MBID),
        }
        mock_repo.find_multi_path_artists.return_value = []
        mock_app = MagicMock()
        mock_app.execute.return_value.scalars.return_value.all.return_value = []

        result = service.get_recommendations(
            mb_session=MagicMock(),
            app_session=mock_app,
            seed_mbid=SEED_MBID,
            user_id=USER_ID,
        )

        assert result["recommendations"] == []
        assert result["filtered_known_artists"] == 0

    def test_includes_params_and_weights(self, service, mock_repo):
        mock_repo.get_artist_by_mbid.return_value = {
            "name": "Seed",
            "mbid": str(SEED_MBID),
        }
        mock_repo.find_multi_path_artists.return_value = []
        mock_app = MagicMock()
        mock_app.execute.return_value.scalars.return_value.all.return_value = []

        result = service.get_recommendations(
            mb_session=MagicMock(),
            app_session=mock_app,
            seed_mbid=SEED_MBID,
            user_id=USER_ID,
            relationship_types=["producer"],
            min_paths=3,
            limit=10,
            weights={
                "path_count": 2.0,
                "genre_affinity": 1.0,
                "collaborator_diversity": 0.0,
            },
        )

        assert result["params"]["relationship_types"] == ["producer"]
        assert result["params"]["weights"]["path_count"] == 2.0

    def test_includes_score_breakdown(self, service, mock_repo):
        mock_repo.get_artist_by_mbid.return_value = {
            "name": "Seed",
            "mbid": str(SEED_MBID),
        }
        mock_repo.find_multi_path_artists.return_value = [
            _make_candidate("Artist A", UNKNOWN_MBID),
        ]
        mock_repo.get_artist_tags.return_value = {
            str(SEED_MBID): {"rock": 5},
            str(UNKNOWN_MBID): {"rock": 3},
        }
        mock_app = MagicMock()
        mock_app.execute.return_value.scalars.return_value.all.return_value = []

        result = service.get_recommendations(
            mb_session=MagicMock(),
            app_session=mock_app,
            seed_mbid=SEED_MBID,
            user_id=USER_ID,
        )

        rec = result["recommendations"][0]
        assert "score" in rec
        assert "path_count" in rec["score"]
        assert "genre_affinity" in rec["score"]
        assert "collaborator_diversity" in rec["score"]
        assert "final_score" in rec["score"]

    def test_sorted_by_final_score(self, service, mock_repo):
        mock_repo.get_artist_by_mbid.return_value = {
            "name": "Seed",
            "mbid": str(SEED_MBID),
        }
        low_mbid = uuid.UUID("00000000-0000-0000-0000-000000000300")
        high_mbid = uuid.UUID("00000000-0000-0000-0000-000000000400")
        mock_repo.find_multi_path_artists.return_value = [
            _make_candidate(
                "Low Score",
                low_mbid,
                path_count=2,
                paths=[
                    {
                        "relationship_type": "producer",
                        "via": "P1",
                        "collaborator_artist_count": 2,
                    },
                    {
                        "relationship_type": "performer",
                        "via": "P2",
                        "collaborator_artist_count": 2,
                    },
                ],
            ),
            _make_candidate(
                "High Score",
                high_mbid,
                path_count=2,
                paths=[
                    {
                        "relationship_type": "producer",
                        "via": "P3",
                        "collaborator_artist_count": 50,
                    },
                    {
                        "relationship_type": "performer",
                        "via": "P4",
                        "collaborator_artist_count": 40,
                    },
                ],
            ),
        ]
        mock_repo.get_artist_tags.return_value = {
            str(SEED_MBID): {"indie rock": 9},
            str(high_mbid): {"indie rock": 7},
        }
        mock_app = MagicMock()
        mock_app.execute.return_value.scalars.return_value.all.return_value = []

        result = service.get_recommendations(
            mb_session=MagicMock(),
            app_session=mock_app,
            seed_mbid=SEED_MBID,
            user_id=USER_ID,
        )

        assert result["recommendations"][0]["artist"]["name"] == "High Score"
        assert result["recommendations"][1]["artist"]["name"] == "Low Score"

    def test_fetches_tags(self, service, mock_repo):
        mock_repo.get_artist_by_mbid.return_value = {
            "name": "Seed",
            "mbid": str(SEED_MBID),
        }
        mock_repo.find_multi_path_artists.return_value = [
            _make_candidate("A", UNKNOWN_MBID),
        ]
        mock_app = MagicMock()
        mock_app.execute.return_value.scalars.return_value.all.return_value = []

        service.get_recommendations(
            mb_session=MagicMock(),
            app_session=mock_app,
            seed_mbid=SEED_MBID,
            user_id=USER_ID,
        )

        mock_repo.get_artist_tags.assert_called_once()
        call_args = mock_repo.get_artist_tags.call_args
        mbids = call_args[0][1]
        assert str(SEED_MBID) in mbids
        assert str(UNKNOWN_MBID) in mbids
