import uuid
from unittest.mock import MagicMock

import pytest

from app.services.discogs import DiscogsSource
from app.services.taste_profile import TasteProfileSnapshot


def _collection_item(title, master_id, artist_name, artist_id=1):
    return {
        "id": 1,
        "basic_information": {
            "title": title,
            "master_id": master_id,
            "artists": [{"id": artist_id, "name": artist_name}],
        },
    }


def _make_source(collection, wantlist, username="tom", access_token="at", secret="ats"):
    mock_client = MagicMock()
    mock_client.get_collection.return_value = collection
    mock_client.get_wantlist.return_value = wantlist
    mock_repo = MagicMock()
    mock_profile = MagicMock()
    mock_profile.discogs_username = username
    mock_profile.access_token = access_token
    mock_profile.access_token_secret = secret
    mock_repo.get_discogs_profile.return_value = mock_profile
    return DiscogsSource(mock_client, mock_repo), mock_client


def test_fetch_returns_snapshot_with_both_periods():
    collection = [_collection_item("X", 10, "A")]
    wantlist = [_collection_item("Y", 20, "B")]
    source, _ = _make_source(collection, wantlist)
    snap = source.fetch(MagicMock(), uuid.uuid4())
    assert isinstance(snap, TasteProfileSnapshot)
    assert snap.source == "discogs"
    assert set(snap.artists_by_period.keys()) == {"collection", "wantlist"}
    assert set(snap.albums_by_period.keys()) == {"collection", "wantlist"}


def test_collection_artist_aggregation_counts_owned_releases():
    collection = [
        _collection_item("A1", 1, "A"),
        _collection_item("A2", 2, "A"),
        _collection_item("A3", 3, "A"),
        _collection_item("B1", 10, "B"),
    ]
    source, _ = _make_source(collection, [])
    snap = source.fetch(MagicMock(), uuid.uuid4())
    artists = snap.artists_by_period["collection"]
    by_name = {a.name: a.count for a in artists}
    assert by_name == {"A": 3, "B": 1}


def test_wantlist_artist_aggregation_counts_wanted_items():
    wantlist = [
        _collection_item("W1", 1, "A"),
        _collection_item("W2", 2, "A"),
    ]
    source, _ = _make_source([], wantlist)
    snap = source.fetch(MagicMock(), uuid.uuid4())
    artists = snap.artists_by_period["wantlist"]
    assert {a.name: a.count for a in artists} == {"A": 2}


def test_albums_dedup_by_artist_and_title_in_collection():
    collection = [
        _collection_item("Same Album", 100, "A"),
        _collection_item("Same Album", 100, "A"),
        _collection_item("Same Album", 100, "A"),
        _collection_item("Other Album", 101, "A"),
    ]
    source, _ = _make_source(collection, [])
    snap = source.fetch(MagicMock(), uuid.uuid4())
    albums = snap.albums_by_period["collection"]
    by_name = {a.name: a.count for a in albums}
    assert by_name == {"Same Album": 3, "Other Album": 1}


def _collection_item_with_format(
    title, master_id, artist_name, descriptions, artist_id=1
):
    item = _collection_item(title, master_id, artist_name, artist_id)
    item["basic_information"]["formats"] = [
        {"name": "Vinyl", "descriptions": descriptions}
    ]
    return item


def test_albums_same_release_type_collapses_distinct_masters():
    # Two "Let It Be" album masters (album vs. single the same DB constraint
    # used to reject) now collapse because they share release_type="album".
    collection = [
        _collection_item_with_format("Let It Be", 100, "The Beatles", ["LP", "Album"]),
        _collection_item_with_format("Let It Be", 200, "The Beatles", ["CD", "Album"]),
    ]
    source, _ = _make_source(collection, [])
    snap = source.fetch(MagicMock(), uuid.uuid4())
    albums = snap.albums_by_period["collection"]
    assert len(albums) == 1
    assert albums[0].name == "Let It Be"
    assert albums[0].release_type == "album"
    assert albums[0].count == 2


def test_albums_different_release_types_stay_distinct():
    # "Let It Be" album and "Let It Be" single by The Beatles must produce
    # two separate entries with their own release_type values.
    collection = [
        _collection_item_with_format("Let It Be", 100, "The Beatles", ["LP", "Album"]),
        _collection_item_with_format("Let It Be", 200, "The Beatles", ['7"', "Single"]),
    ]
    source, _ = _make_source(collection, [])
    snap = source.fetch(MagicMock(), uuid.uuid4())
    albums = snap.albums_by_period["collection"]
    by_type = {(a.name, a.release_type): a.count for a in albums}
    assert by_type == {
        ("Let It Be", "album"): 1,
        ("Let It Be", "single"): 1,
    }


def test_albums_default_release_type_when_no_format_info():
    collection = [_collection_item("Some Album", 300, "Artist")]
    source, _ = _make_source(collection, [])
    snap = source.fetch(MagicMock(), uuid.uuid4())
    assert snap.albums_by_period["collection"][0].release_type == "album"


def test_albums_release_type_from_ep_description():
    collection = [
        _collection_item_with_format("My EP", 400, "Artist", ["EP", "45 RPM"]),
    ]
    source, _ = _make_source(collection, [])
    snap = source.fetch(MagicMock(), uuid.uuid4())
    assert snap.albums_by_period["collection"][0].release_type == "ep"


def test_albums_fallback_when_master_id_null():
    collection = [
        {
            "id": 1,
            "basic_information": {
                "title": "Obscure",
                "master_id": None,
                "artists": [{"id": 1, "name": "Obscurer"}],
            },
        },
        {
            "id": 2,
            "basic_information": {
                "title": "Obscure",
                "master_id": None,
                "artists": [{"id": 1, "name": "Obscurer"}],
            },
        },
    ]
    source, _ = _make_source(collection, [])
    snap = source.fetch(MagicMock(), uuid.uuid4())
    albums = snap.albums_by_period["collection"]
    assert len(albums) == 1
    assert albums[0].count == 2


def test_various_artists_primary_is_skipped():
    collection = [
        {
            "id": 1,
            "basic_information": {
                "title": "Compilation",
                "master_id": 50,
                "artists": [{"id": 194, "name": "Various"}],
            },
        },
        _collection_item("Real Album", 51, "RealArtist", artist_id=5),
    ]
    source, _ = _make_source(collection, [])
    snap = source.fetch(MagicMock(), uuid.uuid4())
    artists = snap.artists_by_period["collection"]
    assert {a.name for a in artists} == {"RealArtist"}
    albums = snap.albums_by_period["collection"]
    assert {a.name for a in albums} == {"Real Album"}


def test_malformed_items_skipped():
    collection = [
        {
            "id": 1,
            "basic_information": {
                "title": "Good",
                "master_id": 1,
                "artists": [{"id": 1, "name": "A"}],
            },
        },
        {"id": 2, "basic_information": {"title": "No artists", "master_id": 2}},
        {"id": 3},  # no basic_information at all
    ]
    source, _ = _make_source(collection, [])
    snap = source.fetch(MagicMock(), uuid.uuid4())
    assert {a.name for a in snap.artists_by_period["collection"]} == {"A"}


def test_fetch_raises_if_unlinked():
    mock_repo = MagicMock()
    mock_repo.get_discogs_profile.return_value = None
    source = DiscogsSource(MagicMock(), mock_repo)
    with pytest.raises(ValueError, match="Discogs account not linked"):
        source.fetch(MagicMock(), uuid.uuid4())


def test_fetch_raises_if_no_access_token():
    mock_repo = MagicMock()
    mock_profile = MagicMock()
    mock_profile.access_token = None
    mock_repo.get_discogs_profile.return_value = mock_profile
    source = DiscogsSource(MagicMock(), mock_repo)
    with pytest.raises(ValueError, match="Discogs account not linked"):
        source.fetch(MagicMock(), uuid.uuid4())
