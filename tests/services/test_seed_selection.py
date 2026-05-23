import random
import uuid

from app.services.seed_selection import select_seeds


def _make_artist(name, mbid=None, playcount=100):
    return {
        "artist_name": name,
        "artist_mbid": mbid or str(uuid.uuid4()),
        "count": playcount,
    }


class TestSelectSeeds:
    def test_selects_requested_number(self):
        artists = [_make_artist(f"Artist {i}", playcount=100) for i in range(20)]
        random.seed(42)
        result = select_seeds(artists, num_seeds=5)
        assert len(result) == 5

    def test_weighted_by_playcount(self):
        heavy = _make_artist("Heavy", playcount=1000)
        light = _make_artist("Light", playcount=1)
        artists = [heavy, light]
        heavy_count = 0
        for i in range(200):
            random.seed(i)
            picks = select_seeds(artists, num_seeds=1)
            if picks[0]["artist_name"] == "Heavy":
                heavy_count += 1
        assert heavy_count > 150

    def test_excludes_artists_without_mbids(self):
        with_mbid = _make_artist("Has MBID", playcount=100)
        without_mbid = {
            "artist_name": "No MBID",
            "artist_mbid": None,
            "count": 500,
        }
        empty_mbid = {
            "artist_name": "Empty MBID",
            "artist_mbid": "",
            "count": 500,
        }
        artists = [with_mbid, without_mbid, empty_mbid]
        result = select_seeds(artists, num_seeds=5)
        assert len(result) == 1
        assert result[0]["artist_name"] == "Has MBID"

    def test_respects_exclude_mbids(self):
        a1 = _make_artist("Artist 1", mbid="mbid-1", playcount=100)
        a2 = _make_artist("Artist 2", mbid="mbid-2", playcount=100)
        a3 = _make_artist("Artist 3", mbid="mbid-3", playcount=100)
        result = select_seeds(
            [a1, a2, a3], num_seeds=5, exclude_mbids={"mbid-1", "mbid-2"}
        )
        assert len(result) == 1
        assert result[0]["artist_name"] == "Artist 3"

    def test_fewer_eligible_than_requested(self):
        artists = [_make_artist(f"Artist {i}") for i in range(3)]
        result = select_seeds(artists, num_seeds=10)
        assert len(result) == 3

    def test_empty_artists_returns_empty(self):
        result = select_seeds([], num_seeds=5)
        assert result == []

    def test_no_duplicates(self):
        artists = [_make_artist(f"Artist {i}", playcount=100) for i in range(5)]
        for i in range(50):
            random.seed(i)
            result = select_seeds(artists, num_seeds=5)
            names = [a["artist_name"] for a in result]
            assert len(names) == len(set(names))

    def test_all_filtered_returns_empty(self):
        artists = [
            {"artist_name": "A", "artist_mbid": None, "count": 100},
        ]
        result = select_seeds(artists, num_seeds=5)
        assert result == []
