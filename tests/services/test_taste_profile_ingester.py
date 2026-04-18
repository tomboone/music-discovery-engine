import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.app import Base, TasteProfileAlbum, TasteProfileArtist, User
from app.services.taste_profile import (
    AlbumEntry,
    ArtistEntry,
    TasteProfileSnapshot,
)
from app.services.taste_profile.ingester import TasteProfileIngester


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


def _stub_source(snapshot):
    class _S:
        def fetch(self, session, user_id):
            return snapshot

    return _S()


def test_ingest_fresh_snapshot_assigns_ranks(session, user_id):
    snap = TasteProfileSnapshot(
        source="discogs",
        artists_by_period={
            "collection": [
                ArtistEntry("A", None, 5),
                ArtistEntry("B", None, 10),
                ArtistEntry("C", None, 3),
            ]
        },
        albums_by_period={"collection": []},
    )
    ingester = TasteProfileIngester()
    result = ingester.ingest(session, user_id, _stub_source(snap))
    session.commit()

    rows = (
        session.query(TasteProfileArtist)
        .filter_by(user_id=user_id, source="discogs", period="collection")
        .order_by(TasteProfileArtist.rank)
        .all()
    )
    assert [r.artist_name for r in rows] == ["B", "A", "C"]
    assert [r.rank for r in rows] == [1, 2, 3]
    assert [r.count for r in rows] == [10, 5, 3]
    assert result["artists_count"] == 3


def test_ingest_replaces_stale_rows_in_same_bucket(session, user_id):
    ingester = TasteProfileIngester()
    first = TasteProfileSnapshot(
        source="discogs",
        artists_by_period={
            "collection": [ArtistEntry("A", None, 5), ArtistEntry("B", None, 10)]
        },
        albums_by_period={"collection": []},
    )
    ingester.ingest(session, user_id, _stub_source(first))
    session.commit()

    second = TasteProfileSnapshot(
        source="discogs",
        artists_by_period={"collection": [ArtistEntry("B", None, 12)]},
        albums_by_period={"collection": []},
    )
    ingester.ingest(session, user_id, _stub_source(second))
    session.commit()

    rows = (
        session.query(TasteProfileArtist)
        .filter_by(user_id=user_id, source="discogs", period="collection")
        .all()
    )
    assert [r.artist_name for r in rows] == ["B"]
    assert rows[0].count == 12


def test_ingest_leaves_other_buckets_untouched(session, user_id):
    ingester = TasteProfileIngester()
    lastfm_snap = TasteProfileSnapshot(
        source="lastfm",
        artists_by_period={"overall": [ArtistEntry("X", None, 100)]},
        albums_by_period={"overall": []},
    )
    ingester.ingest(session, user_id, _stub_source(lastfm_snap))
    session.commit()

    discogs_snap = TasteProfileSnapshot(
        source="discogs",
        artists_by_period={"collection": [ArtistEntry("Y", None, 5)]},
        albums_by_period={"collection": []},
    )
    ingester.ingest(session, user_id, _stub_source(discogs_snap))
    session.commit()

    lastfm_rows = (
        session.query(TasteProfileArtist)
        .filter_by(user_id=user_id, source="lastfm")
        .all()
    )
    assert [r.artist_name for r in lastfm_rows] == ["X"]


def test_ingest_albums(session, user_id):
    snap = TasteProfileSnapshot(
        source="discogs",
        artists_by_period={"collection": []},
        albums_by_period={
            "collection": [
                AlbumEntry("Album One", "Artist A", None, None, 2),
                AlbumEntry("Album Two", "Artist B", None, None, 1),
            ]
        },
    )
    ingester = TasteProfileIngester()
    result = ingester.ingest(session, user_id, _stub_source(snap))
    session.commit()

    rows = (
        session.query(TasteProfileAlbum)
        .filter_by(user_id=user_id, source="discogs", period="collection")
        .order_by(TasteProfileAlbum.rank)
        .all()
    )
    assert [r.album_name for r in rows] == ["Album One", "Album Two"]
    assert [r.count for r in rows] == [2, 1]
    assert result["albums_count"] == 2


def test_ingester_does_not_commit(session, user_id):
    snap = TasteProfileSnapshot(
        source="discogs",
        artists_by_period={"collection": [ArtistEntry("A", None, 1)]},
        albums_by_period={"collection": []},
    )
    ingester = TasteProfileIngester()
    ingester.ingest(session, user_id, _stub_source(snap))
    # No commit yet; rollback should erase
    session.rollback()

    rows = session.query(TasteProfileArtist).filter_by(user_id=user_id).all()
    assert rows == []


def test_ingest_handles_mbid_strings(session, user_id):
    mbid_str = "0cc91378-c306-4b84-b7b8-eaaa8f1b7a6f"
    snap = TasteProfileSnapshot(
        source="lastfm",
        artists_by_period={"overall": [ArtistEntry("YLT", mbid_str, 2500)]},
        albums_by_period={"overall": []},
    )
    ingester = TasteProfileIngester()
    ingester.ingest(session, user_id, _stub_source(snap))
    session.commit()

    row = session.query(TasteProfileArtist).filter_by(user_id=user_id).one()
    assert str(row.artist_mbid) == mbid_str
