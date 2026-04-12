import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.models.app import Base, RecommendationHistory, User
from app.repositories.generation import GenerationRepository


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_recommendation_history_table_schema():
    engine = _engine()
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("recommendation_history")}
    assert columns == {
        "id",
        "user_id",
        "artist_name",
        "artist_mbid",
        "seed_artist_name",
        "seed_artist_mbid",
        "source",
        "recommendation_type",
        "score",
        "created_at",
    }


def test_recommendation_history_creation():
    engine = _engine()
    with Session(engine) as session:
        user = User(id=uuid.uuid4(), email="test@example.com")
        session.add(user)
        session.flush()
        rec = RecommendationHistory(
            id=uuid.uuid4(),
            user_id=user.id,
            artist_name="Josh Rouse",
            artist_mbid=uuid.uuid4(),
            seed_artist_name="Yo La Tengo",
            seed_artist_mbid=uuid.uuid4(),
            source="graph",
            recommendation_type="primary",
            score=3.49,
        )
        session.add(rec)
        session.commit()
        result = session.get(RecommendationHistory, rec.id)
        assert result is not None
        assert result.artist_name == "Josh Rouse"
        assert result.recommendation_type == "primary"


@pytest.fixture
def repo_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def repo_session(repo_engine):
    with Session(repo_engine) as session:
        yield session


@pytest.fixture
def seed_user(repo_session):
    user = User(id=uuid.uuid4(), email="gen_test@example.com")
    repo_session.add(user)
    repo_session.commit()
    return user


class TestSaveRecommendations:
    def test_saves_to_history(self, repo_session, seed_user):
        repo = GenerationRepository()
        recs = [
            {
                "artist_name": "Josh Rouse",
                "artist_mbid": str(uuid.uuid4()),
                "seed_artist_name": "Yo La Tengo",
                "seed_artist_mbid": str(uuid.uuid4()),
                "source": "graph",
                "recommendation_type": "primary",
                "score": 3.49,
            },
            {
                "artist_name": "Lali Puna",
                "artist_mbid": "",
                "seed_artist_name": "The Notwist",
                "seed_artist_mbid": str(uuid.uuid4()),
                "source": "lastfm_similar",
                "recommendation_type": "also_explore",
                "score": 0.87,
            },
        ]
        repo.save_recommendations(repo_session, seed_user.id, recs)
        results = (
            repo_session.query(RecommendationHistory)
            .filter_by(user_id=seed_user.id)
            .all()
        )
        assert len(results) == 2


class TestGetRecentHistory:
    def test_returns_recent_mbids(self, repo_session, seed_user):
        repo = GenerationRepository()
        mbid = uuid.uuid4()
        rec = RecommendationHistory(
            id=uuid.uuid4(),
            user_id=seed_user.id,
            artist_name="Josh Rouse",
            artist_mbid=mbid,
            seed_artist_name="YLT",
            seed_artist_mbid=uuid.uuid4(),
            source="graph",
            recommendation_type="primary",
            score=3.0,
        )
        repo_session.add(rec)
        repo_session.commit()

        history = repo.get_recent_history(repo_session, seed_user.id)
        assert str(mbid) in history

    def test_excludes_old_history(self, repo_session, seed_user):
        repo = GenerationRepository()
        mbid = uuid.uuid4()
        old_rec = RecommendationHistory(
            id=uuid.uuid4(),
            user_id=seed_user.id,
            artist_name="Old Artist",
            artist_mbid=mbid,
            seed_artist_name="YLT",
            seed_artist_mbid=uuid.uuid4(),
            source="graph",
            recommendation_type="primary",
            score=2.0,
            created_at=datetime.now(UTC) - timedelta(days=200),
        )
        repo_session.add(old_rec)
        repo_session.commit()

        history = repo.get_recent_history(repo_session, seed_user.id)
        assert str(mbid) not in history

    def test_name_based_fallback_for_no_mbid(self, repo_session, seed_user):
        repo = GenerationRepository()
        rec = RecommendationHistory(
            id=uuid.uuid4(),
            user_id=seed_user.id,
            artist_name="No MBID Artist",
            artist_mbid=None,
            seed_artist_name="YLT",
            seed_artist_mbid=uuid.uuid4(),
            source="lastfm_similar",
            recommendation_type="also_explore",
            score=0.5,
        )
        repo_session.add(rec)
        repo_session.commit()

        history = repo.get_recent_history(repo_session, seed_user.id)
        assert "name:No MBID Artist" in history

    def test_empty_history(self, repo_session, seed_user):
        repo = GenerationRepository()
        history = repo.get_recent_history(repo_session, seed_user.id)
        assert history == set()
