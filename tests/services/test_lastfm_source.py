import uuid
from unittest.mock import MagicMock

from app.services.lastfm import LastfmSource
from app.services.taste_profile import TasteProfileSnapshot


def test_lastfm_source_fetch_shapes_snapshot():
    mock_client = MagicMock()
    mock_client.get_top_artists.return_value = [
        {
            "name": "A",
            "playcount": "10",
            "mbid": "0cc91378-c306-4b84-b7b8-eaaa8f1b7a6f",
        },
        {"name": "B", "playcount": "5", "mbid": ""},
    ]
    mock_client.get_top_albums.return_value = [
        {
            "name": "Album X",
            "playcount": "3",
            "mbid": "",
            "artist": {"name": "A", "mbid": "0cc91378-c306-4b84-b7b8-eaaa8f1b7a6f"},
        }
    ]
    mock_repo = MagicMock()
    mock_profile = MagicMock()
    mock_profile.lastfm_username = "tom"
    mock_repo.get_lastfm_profile.return_value = mock_profile

    source = LastfmSource(mock_client, mock_repo)
    snap = source.fetch(session=MagicMock(), user_id=uuid.uuid4())

    assert isinstance(snap, TasteProfileSnapshot)
    assert snap.source == "lastfm"
    assert "overall" in snap.artists_by_period
    artists = snap.artists_by_period["overall"]
    assert [a.name for a in artists] == ["A", "B"]
    assert artists[0].count == 10
    assert artists[0].mbid == "0cc91378-c306-4b84-b7b8-eaaa8f1b7a6f"
    assert artists[1].mbid is None  # empty string becomes None

    albums = snap.albums_by_period["overall"]
    assert len(albums) == 1
    assert albums[0].name == "Album X"
    assert albums[0].artist_name == "A"
    assert albums[0].count == 3


def test_lastfm_source_raises_if_unlinked():
    import pytest

    mock_repo = MagicMock()
    mock_repo.get_lastfm_profile.return_value = None
    source = LastfmSource(MagicMock(), mock_repo)
    with pytest.raises(ValueError, match="Last.fm account not linked"):
        source.fetch(session=MagicMock(), user_id=uuid.uuid4())
