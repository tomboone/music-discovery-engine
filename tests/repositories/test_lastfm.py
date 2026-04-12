import uuid

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.models.app import (
    Base,
    LastfmProfile,
    TasteProfileAlbum,
    TasteProfileArtist,
    User,
)
from app.repositories.lastfm import LastfmRepository


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_lastfm_profile_table_schema():
    engine = _engine()
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("lastfm_profiles")}
    assert columns == {
        "id",
        "user_id",
        "lastfm_username",
        "session_key",
        "last_synced_at",
        "created_at",
        "updated_at",
    }


def test_taste_profile_artist_table_schema():
    engine = _engine()
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("taste_profile_artists")}
    assert columns == {
        "id",
        "user_id",
        "source",
        "period",
        "artist_name",
        "artist_mbid",
        "playcount",
        "rank",
        "created_at",
        "updated_at",
    }


def test_taste_profile_album_table_schema():
    engine = _engine()
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("taste_profile_albums")}
    assert columns == {
        "id",
        "user_id",
        "source",
        "period",
        "album_name",
        "album_mbid",
        "artist_name",
        "artist_mbid",
        "playcount",
        "rank",
        "created_at",
        "updated_at",
    }


def test_lastfm_profile_creation():
    engine = _engine()
    with Session(engine) as session:
        user = User(id=uuid.uuid4(), email="test@example.com")
        session.add(user)
        session.flush()
        profile = LastfmProfile(
            id=uuid.uuid4(),
            user_id=user.id,
            lastfm_username="testuser",
            session_key="abc123",
        )
        session.add(profile)
        session.commit()
        result = session.get(LastfmProfile, profile.id)
        assert result is not None
        assert result.lastfm_username == "testuser"
        assert result.session_key == "abc123"


def test_taste_profile_artist_creation():
    engine = _engine()
    with Session(engine) as session:
        user = User(id=uuid.uuid4(), email="test@example.com")
        session.add(user)
        session.flush()
        artist = TasteProfileArtist(
            id=uuid.uuid4(),
            user_id=user.id,
            source="lastfm",
            period="overall",
            artist_name="Yo La Tengo",
            artist_mbid=uuid.UUID("3121f5a6-0854-4a15-a3f3-4bd359073857"),
            playcount=500,
            rank=1,
        )
        session.add(artist)
        session.commit()
        result = session.get(TasteProfileArtist, artist.id)
        assert result is not None
        assert result.artist_name == "Yo La Tengo"
        assert result.playcount == 500


def test_taste_profile_album_creation():
    engine = _engine()
    with Session(engine) as session:
        user = User(id=uuid.uuid4(), email="test@example.com")
        session.add(user)
        session.flush()
        album = TasteProfileAlbum(
            id=uuid.uuid4(),
            user_id=user.id,
            source="lastfm",
            period="overall",
            album_name="I Can Hear the Heart Beating as One",
            album_mbid=uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
            artist_name="Yo La Tengo",
            artist_mbid=uuid.UUID("3121f5a6-0854-4a15-a3f3-4bd359073857"),
            playcount=200,
            rank=1,
        )
        session.add(album)
        session.commit()
        result = session.get(TasteProfileAlbum, album.id)
        assert result is not None
        assert result.album_name == "I Can Hear the Heart Beating as One"
        assert result.artist_name == "Yo La Tengo"


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
    user = User(id=uuid.uuid4(), email="repo_test@example.com")
    repo_session.add(user)
    repo_session.commit()
    return user


class TestSaveLastfmProfile:
    def test_creates_new_profile(self, repo_session, seed_user):
        repo = LastfmRepository()
        profile = repo.save_lastfm_profile(
            repo_session, seed_user.id, "myuser", "session_key_123"
        )
        assert profile.lastfm_username == "myuser"
        assert profile.session_key == "session_key_123"
        assert profile.user_id == seed_user.id

    def test_updates_existing_profile(self, repo_session, seed_user):
        repo = LastfmRepository()
        repo.save_lastfm_profile(repo_session, seed_user.id, "myuser", "key1")
        updated = repo.save_lastfm_profile(repo_session, seed_user.id, "myuser", "key2")
        assert updated.session_key == "key2"
        profiles = (
            repo_session.query(LastfmProfile).filter_by(user_id=seed_user.id).all()
        )
        assert len(profiles) == 1


class TestGetLastfmProfile:
    def test_returns_profile(self, repo_session, seed_user):
        repo = LastfmRepository()
        repo.save_lastfm_profile(repo_session, seed_user.id, "myuser", "key1")
        result = repo.get_lastfm_profile(repo_session, seed_user.id)
        assert result is not None
        assert result.lastfm_username == "myuser"

    def test_returns_none_when_not_found(self, repo_session, seed_user):
        repo = LastfmRepository()
        result = repo.get_lastfm_profile(repo_session, seed_user.id)
        assert result is None


class TestUpsertTopArtists:
    def test_inserts_artists(self, repo_session, seed_user):
        repo = LastfmRepository()
        artists = [
            {
                "name": "Yo La Tengo",
                "mbid": "3121f5a6-0854-4a15-a3f3-4bd359073857",
                "playcount": "500",
                "@attr": {"rank": "1"},
            },
            {
                "name": "Sonic Youth",
                "mbid": "",
                "playcount": "300",
                "@attr": {"rank": "2"},
            },
        ]
        repo.upsert_top_artists(
            repo_session, seed_user.id, "lastfm", "overall", artists
        )
        results = (
            repo_session.query(TasteProfileArtist).filter_by(user_id=seed_user.id).all()
        )
        assert len(results) == 2
        assert results[0].artist_name == "Yo La Tengo"
        assert results[1].artist_mbid is None  # empty string -> None

    def test_updates_playcount_on_resync(self, repo_session, seed_user):
        repo = LastfmRepository()
        artists_v1 = [
            {
                "name": "Yo La Tengo",
                "mbid": "",
                "playcount": "500",
                "@attr": {"rank": "1"},
            },
        ]
        repo.upsert_top_artists(
            repo_session, seed_user.id, "lastfm", "overall", artists_v1
        )
        artists_v2 = [
            {
                "name": "Yo La Tengo",
                "mbid": "",
                "playcount": "600",
                "@attr": {"rank": "1"},
            },
        ]
        repo.upsert_top_artists(
            repo_session, seed_user.id, "lastfm", "overall", artists_v2
        )
        results = (
            repo_session.query(TasteProfileArtist).filter_by(user_id=seed_user.id).all()
        )
        assert len(results) == 1
        assert results[0].playcount == 600

    def test_deletes_stale_artists(self, repo_session, seed_user):
        repo = LastfmRepository()
        artists_v1 = [
            {
                "name": "Yo La Tengo",
                "mbid": "",
                "playcount": "500",
                "@attr": {"rank": "1"},
            },
            {
                "name": "Sonic Youth",
                "mbid": "",
                "playcount": "300",
                "@attr": {"rank": "2"},
            },
        ]
        repo.upsert_top_artists(
            repo_session, seed_user.id, "lastfm", "overall", artists_v1
        )
        artists_v2 = [
            {
                "name": "Yo La Tengo",
                "mbid": "",
                "playcount": "600",
                "@attr": {"rank": "1"},
            },
        ]
        repo.upsert_top_artists(
            repo_session, seed_user.id, "lastfm", "overall", artists_v2
        )
        results = (
            repo_session.query(TasteProfileArtist).filter_by(user_id=seed_user.id).all()
        )
        assert len(results) == 1
        assert results[0].artist_name == "Yo La Tengo"


class TestUpsertTopAlbums:
    def test_inserts_albums(self, repo_session, seed_user):
        repo = LastfmRepository()
        albums = [
            {
                "name": "I Can Hear the Heart Beating as One",
                "mbid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "playcount": "200",
                "artist": {
                    "name": "Yo La Tengo",
                    "mbid": "3121f5a6-0854-4a15-a3f3-4bd359073857",
                },
                "@attr": {"rank": "1"},
            }
        ]
        repo.upsert_top_albums(repo_session, seed_user.id, "lastfm", "overall", albums)
        results = (
            repo_session.query(TasteProfileAlbum).filter_by(user_id=seed_user.id).all()
        )
        assert len(results) == 1
        assert results[0].album_name == "I Can Hear the Heart Beating as One"
        assert results[0].artist_name == "Yo La Tengo"

    def test_deletes_stale_albums(self, repo_session, seed_user):
        repo = LastfmRepository()
        albums_v1 = [
            {
                "name": "Album1",
                "mbid": "",
                "playcount": "100",
                "artist": {"name": "A1", "mbid": ""},
                "@attr": {"rank": "1"},
            },
            {
                "name": "Album2",
                "mbid": "",
                "playcount": "50",
                "artist": {"name": "A2", "mbid": ""},
                "@attr": {"rank": "2"},
            },
        ]
        repo.upsert_top_albums(
            repo_session, seed_user.id, "lastfm", "overall", albums_v1
        )
        albums_v2 = [
            {
                "name": "Album1",
                "mbid": "",
                "playcount": "150",
                "artist": {"name": "A1", "mbid": ""},
                "@attr": {"rank": "1"},
            },
        ]
        repo.upsert_top_albums(
            repo_session, seed_user.id, "lastfm", "overall", albums_v2
        )
        results = (
            repo_session.query(TasteProfileAlbum).filter_by(user_id=seed_user.id).all()
        )
        assert len(results) == 1
