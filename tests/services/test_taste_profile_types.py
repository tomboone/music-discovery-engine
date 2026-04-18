from dataclasses import is_dataclass

from app.services.taste_profile import (
    AlbumEntry,
    ArtistEntry,
    TasteProfileSnapshot,
    TasteProfileSource,
)


def test_artist_entry_shape():
    assert is_dataclass(ArtistEntry)
    e = ArtistEntry(name="Yo La Tengo", mbid=None, count=12)
    assert e.name == "Yo La Tengo"
    assert e.count == 12
    assert e.mbid is None


def test_album_entry_shape():
    assert is_dataclass(AlbumEntry)
    e = AlbumEntry(
        name="I Can Hear the Heart Beating as One",
        artist_name="Yo La Tengo",
        mbid=None,
        artist_mbid=None,
        count=1,
    )
    assert e.name.startswith("I Can Hear")


def test_snapshot_shape():
    snap = TasteProfileSnapshot(
        source="lastfm",
        artists_by_period={"overall": [ArtistEntry("x", None, 1)]},
        albums_by_period={"overall": []},
    )
    assert snap.source == "lastfm"
    assert snap.artists_by_period["overall"][0].name == "x"


def test_source_is_protocol():
    import uuid as _uuid

    class _Dummy:
        def fetch(self, session, user_id):
            return TasteProfileSnapshot(
                source="x", artists_by_period={}, albums_by_period={}
            )

    d: TasteProfileSource = _Dummy()
    assert d.fetch(None, _uuid.uuid4()).source == "x"
