import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.services.generation import GenerationService

USER_ID = uuid.UUID("d4e5f6a7-b8c9-4d0e-a1f2-b3c4d5e6f7a8")
SEED1_MBID = "00000000-0000-0000-0000-000000000001"
SEED2_MBID = "00000000-0000-0000-0000-000000000002"
SEED3_MBID = "00000000-0000-0000-0000-000000000003"


def _taste_artist(name, mbid, playcount=100):
    return MagicMock(
        artist_name=name,
        artist_mbid=uuid.UUID(mbid) if mbid else None,
        playcount=playcount,
    )


def _graph_rec(name, mbid, score, seed_name, seed_mbid):
    return {
        "artist": {"name": name, "mbid": mbid},
        "path_count": 2,
        "paths": [
            {
                "relationship_type": "producer",
                "via": "P1",
                "collaborator_artist_count": 10,
            }
        ],
        "score": {
            "path_count": 2,
            "genre_affinity": 0.5,
            "collaborator_diversity": 0.3,
            "final_score": score,
        },
    }


def _fallback_rec(name, mbid, match):
    return {
        "artist": {"name": name, "mbid": mbid},
        "match": match,
        "source": "lastfm_similar",
    }


@pytest.fixture
def mock_rec_service():
    return MagicMock()


@pytest.fixture
def mock_gen_repo():
    repo = MagicMock()
    repo.get_recent_history.return_value = set()
    return repo


@pytest.fixture
def service(mock_rec_service, mock_gen_repo):
    return GenerationService(
        recommendation_service=mock_rec_service,
        repository=mock_gen_repo,
    )


def _setup_taste_profile(mock_app_session, artists):
    mock_app_session.execute.return_value.scalars.return_value.all.return_value = (
        artists
    )


def _setup_rec_service(mock_rec_service, seed_results):
    def side_effect(**kwargs):
        seed = str(kwargs["seed_mbid"])
        return seed_results.get(seed)

    mock_rec_service.get_recommendations.side_effect = side_effect


class TestGenerate:
    def test_full_pipeline(self, service, mock_rec_service, mock_gen_repo):
        mock_mb = MagicMock()
        mock_app = MagicMock()
        _setup_taste_profile(
            mock_app,
            [
                _taste_artist("Yo La Tengo", SEED1_MBID, 500),
                _taste_artist("The Notwist", SEED2_MBID, 300),
                _taste_artist("Deerhunter", SEED3_MBID, 200),
            ],
        )
        _setup_rec_service(
            mock_rec_service,
            {
                SEED1_MBID: {
                    "seed_artist": {"name": "Yo La Tengo", "mbid": SEED1_MBID},
                    "recommendations": [
                        _graph_rec(
                            "Josh Rouse", "aaa", 3.49, "Yo La Tengo", SEED1_MBID
                        ),
                        _graph_rec(
                            "Sleater-Kinney", "bbb", 2.26, "Yo La Tengo", SEED1_MBID
                        ),
                    ],
                    "fallback_recommendations": [],
                    "fallback_reason": None,
                    "params": {},
                    "filtered_known_artists": 0,
                },
                SEED2_MBID: {
                    "seed_artist": {"name": "The Notwist", "mbid": SEED2_MBID},
                    "recommendations": [],
                    "fallback_recommendations": [
                        _fallback_rec("Lali Puna", "ccc", 0.87),
                    ],
                    "fallback_reason": "graph_results_below_threshold",
                    "params": {},
                    "filtered_known_artists": 0,
                },
                SEED3_MBID: {
                    "seed_artist": {"name": "Deerhunter", "mbid": SEED3_MBID},
                    "recommendations": [
                        _graph_rec("Atlas Sound", "ddd", 2.8, "Deerhunter", SEED3_MBID),
                    ],
                    "fallback_recommendations": [],
                    "fallback_reason": None,
                    "params": {},
                    "filtered_known_artists": 0,
                },
            },
        )

        with patch("app.services.generation.select_seeds") as mock_select:
            mock_select.return_value = [
                {
                    "artist_name": "Yo La Tengo",
                    "artist_mbid": SEED1_MBID,
                    "playcount": 500,
                },
                {
                    "artist_name": "The Notwist",
                    "artist_mbid": SEED2_MBID,
                    "playcount": 300,
                },
                {
                    "artist_name": "Deerhunter",
                    "artist_mbid": SEED3_MBID,
                    "playcount": 200,
                },
            ]
            result = service.generate(
                mb_session=mock_mb,
                app_session=mock_app,
                user_id=USER_ID,
                num_seeds=3,
                num_also_explore=3,
            )

        assert result["primary"] is not None
        assert result["primary"]["artist"]["name"] == "Josh Rouse"
        assert result["primary"]["seed_artist"]["name"] == "Yo La Tengo"
        assert len(result["also_explore"]) >= 1
        assert result["metadata"]["seeds_used"] is not None
        mock_gen_repo.save_recommendations.assert_called_once()

    def test_deduplicates_across_seeds(self, service, mock_rec_service, mock_gen_repo):
        mock_mb = MagicMock()
        mock_app = MagicMock()
        _setup_taste_profile(
            mock_app,
            [
                _taste_artist("Seed1", SEED1_MBID, 500),
                _taste_artist("Seed2", SEED2_MBID, 300),
            ],
        )
        _setup_rec_service(
            mock_rec_service,
            {
                SEED1_MBID: {
                    "seed_artist": {"name": "Seed1", "mbid": SEED1_MBID},
                    "recommendations": [
                        _graph_rec("Overlap Artist", "xxx", 2.0, "Seed1", SEED1_MBID),
                    ],
                    "fallback_recommendations": [],
                    "fallback_reason": None,
                    "params": {},
                    "filtered_known_artists": 0,
                },
                SEED2_MBID: {
                    "seed_artist": {"name": "Seed2", "mbid": SEED2_MBID},
                    "recommendations": [
                        _graph_rec("Overlap Artist", "xxx", 3.0, "Seed2", SEED2_MBID),
                    ],
                    "fallback_recommendations": [],
                    "fallback_reason": None,
                    "params": {},
                    "filtered_known_artists": 0,
                },
            },
        )

        with patch("app.services.generation.select_seeds") as mock_select:
            mock_select.return_value = [
                {"artist_name": "Seed1", "artist_mbid": SEED1_MBID, "playcount": 500},
                {"artist_name": "Seed2", "artist_mbid": SEED2_MBID, "playcount": 300},
            ]
            result = service.generate(
                mb_session=mock_mb,
                app_session=mock_app,
                user_id=USER_ID,
                num_seeds=2,
                num_also_explore=2,
            )

        all_names = []
        if result["primary"]:
            all_names.append(result["primary"]["artist"]["name"])
        all_names.extend(r["artist"]["name"] for r in result["also_explore"])
        assert all_names.count("Overlap Artist") == 1

    def test_filters_history(self, service, mock_rec_service, mock_gen_repo):
        mock_mb = MagicMock()
        mock_app = MagicMock()
        _setup_taste_profile(
            mock_app,
            [
                _taste_artist("Seed1", SEED1_MBID, 500),
            ],
        )
        mock_gen_repo.get_recent_history.return_value = {"embargoed-mbid"}
        _setup_rec_service(
            mock_rec_service,
            {
                SEED1_MBID: {
                    "seed_artist": {"name": "Seed1", "mbid": SEED1_MBID},
                    "recommendations": [
                        _graph_rec(
                            "Embargoed", "embargoed-mbid", 5.0, "Seed1", SEED1_MBID
                        ),
                        _graph_rec("Fresh", "fresh-mbid", 3.0, "Seed1", SEED1_MBID),
                    ],
                    "fallback_recommendations": [],
                    "fallback_reason": None,
                    "params": {},
                    "filtered_known_artists": 0,
                },
            },
        )

        with patch("app.services.generation.select_seeds") as mock_select:
            mock_select.return_value = [
                {"artist_name": "Seed1", "artist_mbid": SEED1_MBID, "playcount": 500},
            ]
            result = service.generate(
                mb_session=mock_mb,
                app_session=mock_app,
                user_id=USER_ID,
                num_seeds=1,
                num_also_explore=2,
            )

        assert result["primary"]["artist"]["name"] == "Fresh"

    def test_also_explore_prefers_different_seeds(
        self, service, mock_rec_service, mock_gen_repo
    ):
        mock_mb = MagicMock()
        mock_app = MagicMock()
        _setup_taste_profile(
            mock_app,
            [
                _taste_artist("Seed1", SEED1_MBID, 500),
                _taste_artist("Seed2", SEED2_MBID, 300),
            ],
        )
        _setup_rec_service(
            mock_rec_service,
            {
                SEED1_MBID: {
                    "seed_artist": {"name": "Seed1", "mbid": SEED1_MBID},
                    "recommendations": [
                        _graph_rec("Best Overall", "aaa", 5.0, "Seed1", SEED1_MBID),
                        _graph_rec("Also From Seed1", "bbb", 4.0, "Seed1", SEED1_MBID),
                    ],
                    "fallback_recommendations": [],
                    "fallback_reason": None,
                    "params": {},
                    "filtered_known_artists": 0,
                },
                SEED2_MBID: {
                    "seed_artist": {"name": "Seed2", "mbid": SEED2_MBID},
                    "recommendations": [
                        _graph_rec("From Seed2", "ccc", 3.0, "Seed2", SEED2_MBID),
                    ],
                    "fallback_recommendations": [],
                    "fallback_reason": None,
                    "params": {},
                    "filtered_known_artists": 0,
                },
            },
        )

        with patch("app.services.generation.select_seeds") as mock_select:
            mock_select.return_value = [
                {"artist_name": "Seed1", "artist_mbid": SEED1_MBID, "playcount": 500},
                {"artist_name": "Seed2", "artist_mbid": SEED2_MBID, "playcount": 300},
            ]
            result = service.generate(
                mb_session=mock_mb,
                app_session=mock_app,
                user_id=USER_ID,
                num_seeds=2,
                num_also_explore=2,
            )

        assert result["primary"]["artist"]["name"] == "Best Overall"
        also_names = [r["artist"]["name"] for r in result["also_explore"]]
        assert "From Seed2" in also_names

    def test_empty_taste_profile_returns_error(
        self, service, mock_rec_service, mock_gen_repo
    ):
        mock_mb = MagicMock()
        mock_app = MagicMock()
        _setup_taste_profile(mock_app, [])
        result = service.generate(
            mb_session=mock_mb,
            app_session=mock_app,
            user_id=USER_ID,
        )
        assert "error" in result
        assert result["error"] == "no_taste_profile"

    def test_persists_to_history(self, service, mock_rec_service, mock_gen_repo):
        mock_mb = MagicMock()
        mock_app = MagicMock()
        _setup_taste_profile(
            mock_app,
            [
                _taste_artist("Seed1", SEED1_MBID, 500),
            ],
        )
        _setup_rec_service(
            mock_rec_service,
            {
                SEED1_MBID: {
                    "seed_artist": {"name": "Seed1", "mbid": SEED1_MBID},
                    "recommendations": [
                        _graph_rec("Rec1", "aaa", 3.0, "Seed1", SEED1_MBID),
                    ],
                    "fallback_recommendations": [],
                    "fallback_reason": None,
                    "params": {},
                    "filtered_known_artists": 0,
                },
            },
        )

        with patch("app.services.generation.select_seeds") as mock_select:
            mock_select.return_value = [
                {"artist_name": "Seed1", "artist_mbid": SEED1_MBID, "playcount": 500},
            ]
            service.generate(
                mb_session=mock_mb,
                app_session=mock_app,
                user_id=USER_ID,
                num_seeds=1,
                num_also_explore=0,
            )

        mock_gen_repo.save_recommendations.assert_called_once()
        saved = mock_gen_repo.save_recommendations.call_args[0][2]
        assert len(saved) >= 1
        assert saved[0]["artist_name"] == "Rec1"
        assert saved[0]["recommendation_type"] == "primary"
