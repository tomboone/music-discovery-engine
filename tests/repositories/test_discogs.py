import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.app import Base, DiscogsProfile, User
from app.repositories.discogs import DiscogsRepository


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def user_id(session):
    uid = uuid.uuid4()
    session.add(User(id=uid, email="t@example.com"))
    session.commit()
    return uid


def test_save_request_token_creates_row(session, user_id):
    repo = DiscogsRepository()
    profile = repo.save_request_token(session, user_id, "rt_x", "rts_y")
    assert profile.request_token == "rt_x"
    assert profile.request_token_secret == "rts_y"
    assert profile.access_token is None


def test_save_request_token_updates_existing(session, user_id):
    repo = DiscogsRepository()
    repo.save_request_token(session, user_id, "rt_a", "rts_a")
    profile = repo.save_request_token(session, user_id, "rt_b", "rts_b")
    assert profile.request_token == "rt_b"
    all_rows = session.query(DiscogsProfile).filter_by(user_id=user_id).all()
    assert len(all_rows) == 1


def test_get_profile_by_request_token(session, user_id):
    repo = DiscogsRepository()
    repo.save_request_token(session, user_id, "rt_lookup", "rts_lookup")
    profile = repo.get_profile_by_request_token(session, "rt_lookup")
    assert profile is not None
    assert profile.user_id == user_id


def test_get_profile_by_request_token_returns_none_when_missing(session):
    repo = DiscogsRepository()
    assert repo.get_profile_by_request_token(session, "rt_nope") is None


def test_save_access_token_promotes_profile(session, user_id):
    repo = DiscogsRepository()
    repo.save_request_token(session, user_id, "rt_x", "rts_y")
    profile = repo.save_access_token(
        session,
        user_id,
        access_token="at_new",
        access_token_secret="ats_new",
        username="tom",
    )
    assert profile.access_token == "at_new"
    assert profile.access_token_secret == "ats_new"
    assert profile.discogs_username == "tom"
    assert profile.request_token is None
    assert profile.request_token_secret is None


def test_get_discogs_profile(session, user_id):
    repo = DiscogsRepository()
    assert repo.get_discogs_profile(session, user_id) is None
    repo.save_request_token(session, user_id, "rt", "rts")
    profile = repo.get_discogs_profile(session, user_id)
    assert profile is not None


def test_clear_access_token(session, user_id):
    repo = DiscogsRepository()
    repo.save_request_token(session, user_id, "rt", "rts")
    repo.save_access_token(session, user_id, "at", "ats", "tom")
    repo.clear_access_token(session, user_id)
    profile = repo.get_discogs_profile(session, user_id)
    assert profile is not None
    assert profile.access_token is None
    assert profile.access_token_secret is None
    assert profile.discogs_username == "tom"  # retained for UX
