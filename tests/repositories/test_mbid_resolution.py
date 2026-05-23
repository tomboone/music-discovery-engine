import unicodedata
import uuid

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from app.models.app import Base, TasteProfileArtist, User
from app.repositories.mbid_resolution import MbidResolutionRepository


def _register_unaccent(dbapi_connection, _connection_record):
    """Register MB's ``musicbrainz_unaccent`` SQL function for SQLite tests."""

    def unaccent(s):
        if s is None:
            return None
        return "".join(
            c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
        )

    dbapi_connection.create_function("musicbrainz_unaccent", 1, unaccent)


@pytest.fixture
def app_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def mb_session():
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _register_unaccent)
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE artist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gid VARCHAR(36) NOT NULL UNIQUE,
                    name VARCHAR NOT NULL,
                    comment VARCHAR NOT NULL DEFAULT ''
                )
                """
            )
        )
        conn.commit()
    with Session(engine) as s:
        yield s


@pytest.fixture
def user_id(app_session):
    uid = uuid.uuid4()
    app_session.add(User(id=uid, email="t@example.com"))
    app_session.commit()
    return uid


def _insert_mb_artist(mb_session, gid, name, comment=""):
    mb_session.execute(
        text("INSERT INTO artist (gid, name, comment) VALUES (:g, :n, :c)"),
        {"g": str(gid), "n": name, "c": comment},
    )
    mb_session.commit()


def _add_taste_artist(
    app_session,
    user_id,
    name,
    mbid=None,
    source="lastfm",
    period="overall",
    count=10,
    rank=1,
):
    app_session.add(
        TasteProfileArtist(
            id=uuid.uuid4(),
            user_id=user_id,
            source=source,
            period=period,
            artist_name=name,
            artist_mbid=mbid,
            count=count,
            rank=rank,
        )
    )
    app_session.commit()


def test_find_unresolved_artist_names_returns_null_rows_only(app_session, user_id):
    _add_taste_artist(app_session, user_id, "Resolved", mbid=uuid.uuid4())
    _add_taste_artist(app_session, user_id, "Unresolved", mbid=None)
    repo = MbidResolutionRepository()
    names = repo.find_unresolved_artist_names(app_session, user_id)
    assert names == ["Unresolved"]


def test_find_unresolved_artist_names_dedupes_across_sources(app_session, user_id):
    _add_taste_artist(app_session, user_id, "Yo La Tengo", source="lastfm", rank=1)
    _add_taste_artist(
        app_session,
        user_id,
        "Yo La Tengo",
        source="discogs",
        period="collection",
        rank=1,
    )
    repo = MbidResolutionRepository()
    names = repo.find_unresolved_artist_names(app_session, user_id)
    assert names == ["Yo La Tengo"]


def test_find_unresolved_artist_names_excludes_other_users(app_session, user_id):
    other_user = uuid.uuid4()
    app_session.add(User(id=other_user, email="o@example.com"))
    app_session.commit()
    _add_taste_artist(app_session, user_id, "Mine")
    _add_taste_artist(app_session, other_user, "Theirs")
    repo = MbidResolutionRepository()
    names = repo.find_unresolved_artist_names(app_session, user_id)
    assert names == ["Mine"]


def test_find_artist_gid_returns_gid_for_unambiguous_match(mb_session):
    gid = uuid.uuid4()
    _insert_mb_artist(mb_session, gid, "Yo La Tengo", comment="")
    repo = MbidResolutionRepository()
    result = repo.find_artist_gid(mb_session, "Yo La Tengo")
    assert result == gid


def test_find_artist_gid_returns_none_when_no_match(mb_session):
    repo = MbidResolutionRepository()
    assert repo.find_artist_gid(mb_session, "Nonexistent Artist") is None


def test_find_artist_gid_returns_none_when_only_disambiguated_rows_exist(mb_session):
    _insert_mb_artist(mb_session, uuid.uuid4(), "Drake", comment="Canadian rapper")
    _insert_mb_artist(mb_session, uuid.uuid4(), "Drake", comment="English singer")
    repo = MbidResolutionRepository()
    assert repo.find_artist_gid(mb_session, "Drake") is None


def test_find_artist_gid_returns_none_when_multiple_rows_match(mb_session):
    _insert_mb_artist(mb_session, uuid.uuid4(), "Ambiguous", comment="")
    _insert_mb_artist(mb_session, uuid.uuid4(), "ambiguous", comment="")
    repo = MbidResolutionRepository()
    assert repo.find_artist_gid(mb_session, "Ambiguous") is None


def test_find_artist_gid_matches_case_insensitively(mb_session):
    gid = uuid.uuid4()
    _insert_mb_artist(mb_session, gid, "Yo La Tengo", comment="")
    repo = MbidResolutionRepository()
    assert repo.find_artist_gid(mb_session, "yo la tengo") == gid
    assert repo.find_artist_gid(mb_session, "YO LA TENGO") == gid


def test_find_artist_gid_matches_accent_insensitively(mb_session):
    gid = uuid.uuid4()
    _insert_mb_artist(mb_session, gid, "Björk", comment="")
    repo = MbidResolutionRepository()
    assert repo.find_artist_gid(mb_session, "Bjork") == gid


def test_update_artist_mbids_updates_matching_rows(app_session, user_id):
    _add_taste_artist(app_session, user_id, "Yo La Tengo", source="lastfm", rank=1)
    _add_taste_artist(
        app_session,
        user_id,
        "Yo La Tengo",
        source="discogs",
        period="collection",
        rank=1,
    )
    gid = uuid.uuid4()
    repo = MbidResolutionRepository()
    repo.update_artist_mbids(app_session, user_id, {"Yo La Tengo": gid})
    app_session.commit()

    rows = (
        app_session.query(TasteProfileArtist)
        .filter_by(user_id=user_id, artist_name="Yo La Tengo")
        .all()
    )
    assert len(rows) == 2
    assert all(row.artist_mbid == gid for row in rows)


def test_update_artist_mbids_does_not_clobber_already_resolved_rows(
    app_session, user_id
):
    existing_gid = uuid.uuid4()
    new_gid = uuid.uuid4()
    _add_taste_artist(
        app_session, user_id, "Partial", mbid=existing_gid, source="lastfm"
    )
    _add_taste_artist(
        app_session,
        user_id,
        "Partial",
        mbid=None,
        source="discogs",
        period="collection",
        rank=1,
    )

    repo = MbidResolutionRepository()
    repo.update_artist_mbids(app_session, user_id, {"Partial": new_gid})
    app_session.commit()

    rows = (
        app_session.query(TasteProfileArtist)
        .filter_by(user_id=user_id, artist_name="Partial")
        .order_by(TasteProfileArtist.source)
        .all()
    )
    by_source = {row.source: row.artist_mbid for row in rows}
    assert by_source == {"discogs": new_gid, "lastfm": existing_gid}


def test_update_artist_mbids_does_not_commit(app_session, user_id):
    _add_taste_artist(app_session, user_id, "Ephemeral")
    gid = uuid.uuid4()
    repo = MbidResolutionRepository()
    repo.update_artist_mbids(app_session, user_id, {"Ephemeral": gid})
    app_session.rollback()

    row = (
        app_session.query(TasteProfileArtist)
        .filter_by(user_id=user_id, artist_name="Ephemeral")
        .one()
    )
    assert row.artist_mbid is None


def test_update_artist_mbids_no_resolutions_is_a_noop(app_session, user_id):
    _add_taste_artist(app_session, user_id, "Untouched")
    repo = MbidResolutionRepository()
    result = repo.update_artist_mbids(app_session, user_id, {})
    app_session.commit()
    assert result == 0
