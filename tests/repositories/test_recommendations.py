import uuid

import pytest
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    text,
)
from sqlalchemy.orm import Session

from app.repositories.recommendations import RecommendationRepository

metadata = MetaData(schema="musicbrainz")

artist_table = Table(
    "artist",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("gid", String(36), unique=True),
    Column("name", String(255)),
)

artist_credit_table = Table(
    "artist_credit",
    metadata,
    Column("id", Integer, primary_key=True),
)

artist_credit_name_table = Table(
    "artist_credit_name",
    metadata,
    Column("artist_credit", Integer, ForeignKey("musicbrainz.artist_credit.id")),
    Column("artist", Integer, ForeignKey("musicbrainz.artist.id")),
)

recording_table = Table(
    "recording",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(255)),
    Column("artist_credit", Integer, ForeignKey("musicbrainz.artist_credit.id")),
)

link_type_table = Table(
    "link_type",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(255)),
)

link_table = Table(
    "link",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("link_type", Integer, ForeignKey("musicbrainz.link_type.id")),
)

l_artist_recording_table = Table(
    "l_artist_recording",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("entity0", Integer, ForeignKey("musicbrainz.artist.id")),
    Column("entity1", Integer, ForeignKey("musicbrainz.recording.id")),
    Column("link", Integer, ForeignKey("musicbrainz.link.id")),
)

l_artist_artist_table = Table(
    "l_artist_artist",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("entity0", Integer, ForeignKey("musicbrainz.artist.id")),
    Column("entity1", Integer, ForeignKey("musicbrainz.artist.id")),
    Column("link", Integer, ForeignKey("musicbrainz.link.id")),
)

tag_table = Table(
    "tag",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(255)),
)

artist_tag_table = Table(
    "artist_tag",
    metadata,
    Column("artist", Integer, ForeignKey("musicbrainz.artist.id")),
    Column("tag", Integer, ForeignKey("musicbrainz.tag.id")),
    Column("count", Integer),
)

SEED_GID = "00000000-0000-0000-0000-000000000001"
PRODUCER_GID = "00000000-0000-0000-0000-000000000010"
PERFORMER_GID = "00000000-0000-0000-0000-000000000020"
ARTIST_X_GID = "00000000-0000-0000-0000-000000000100"
ARTIST_Y_GID = "00000000-0000-0000-0000-000000000200"
ARTIST_Z_GID = "00000000-0000-0000-0000-000000000300"


@pytest.fixture
def mb_engine():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("ATTACH DATABASE ':memory:' AS musicbrainz"))
        conn.commit()
    metadata.create_all(engine)
    return engine


@pytest.fixture
def mb_session(mb_engine):
    with Session(mb_engine) as session:
        yield session


@pytest.fixture
def seeded_session(mb_session):
    s = mb_session

    s.execute(link_type_table.insert().values(id=1, name="producer"))
    s.execute(link_type_table.insert().values(id=2, name="performer"))

    s.execute(link_table.insert().values(id=1, link_type=1))
    s.execute(link_table.insert().values(id=2, link_type=2))

    s.execute(artist_table.insert().values(id=1, gid=SEED_GID, name="Seed Artist"))
    s.execute(
        artist_table.insert().values(id=10, gid=PRODUCER_GID, name="The Producer")
    )
    s.execute(
        artist_table.insert().values(id=20, gid=PERFORMER_GID, name="The Performer")
    )
    s.execute(artist_table.insert().values(id=100, gid=ARTIST_X_GID, name="Artist X"))
    s.execute(artist_table.insert().values(id=200, gid=ARTIST_Y_GID, name="Artist Y"))
    s.execute(artist_table.insert().values(id=300, gid=ARTIST_Z_GID, name="Artist Z"))

    s.execute(artist_credit_table.insert().values(id=1))
    s.execute(artist_credit_table.insert().values(id=100))
    s.execute(artist_credit_table.insert().values(id=200))
    s.execute(artist_credit_table.insert().values(id=300))

    s.execute(artist_credit_name_table.insert().values(artist_credit=1, artist=1))
    s.execute(artist_credit_name_table.insert().values(artist_credit=100, artist=100))
    s.execute(artist_credit_name_table.insert().values(artist_credit=200, artist=200))
    s.execute(artist_credit_name_table.insert().values(artist_credit=300, artist=300))

    s.execute(recording_table.insert().values(id=1, name="Seed Rec 1", artist_credit=1))
    s.execute(recording_table.insert().values(id=2, name="Seed Rec 2", artist_credit=1))
    s.execute(
        recording_table.insert().values(id=3, name="X via Producer", artist_credit=100)
    )
    s.execute(
        recording_table.insert().values(id=4, name="Y via Producer", artist_credit=200)
    )
    s.execute(
        recording_table.insert().values(id=5, name="X via Performer", artist_credit=100)
    )
    s.execute(
        recording_table.insert().values(id=6, name="Z via Performer", artist_credit=300)
    )

    s.execute(
        l_artist_recording_table.insert().values(id=1, entity0=10, entity1=1, link=1)
    )
    s.execute(
        l_artist_recording_table.insert().values(id=2, entity0=10, entity1=2, link=1)
    )
    s.execute(
        l_artist_recording_table.insert().values(id=3, entity0=10, entity1=3, link=1)
    )
    s.execute(
        l_artist_recording_table.insert().values(id=4, entity0=10, entity1=4, link=1)
    )
    s.execute(
        l_artist_recording_table.insert().values(id=5, entity0=20, entity1=1, link=2)
    )
    s.execute(
        l_artist_recording_table.insert().values(id=6, entity0=20, entity1=2, link=2)
    )
    s.execute(
        l_artist_recording_table.insert().values(id=7, entity0=20, entity1=5, link=2)
    )
    s.execute(
        l_artist_recording_table.insert().values(id=8, entity0=20, entity1=6, link=2)
    )
    s.execute(
        l_artist_recording_table.insert().values(id=9, entity0=10, entity1=6, link=1)
    )

    # "member of band" link type + link + relationship: Artist Y is member of Seed
    s.execute(link_type_table.insert().values(id=3, name="member of band"))
    s.execute(link_table.insert().values(id=3, link_type=3))
    s.execute(
        l_artist_artist_table.insert().values(id=1, entity0=200, entity1=1, link=3)
    )

    # Tags
    s.execute(tag_table.insert().values(id=1, name="indie rock"))
    s.execute(tag_table.insert().values(id=2, name="noise pop"))
    s.execute(tag_table.insert().values(id=3, name="jazz"))
    s.execute(artist_tag_table.insert().values(artist=1, tag=1, count=9))
    s.execute(artist_tag_table.insert().values(artist=1, tag=2, count=5))
    s.execute(artist_tag_table.insert().values(artist=100, tag=1, count=7))
    s.execute(artist_tag_table.insert().values(artist=200, tag=3, count=10))
    s.execute(artist_tag_table.insert().values(artist=300, tag=1, count=3))
    s.execute(artist_tag_table.insert().values(artist=300, tag=2, count=2))

    s.commit()
    return s


class TestFindMultiPathArtists:
    def test_finds_artist_with_multiple_paths(self, seeded_session):
        repo = RecommendationRepository()
        results = repo.find_multi_path_artists(
            seeded_session,
            seed_mbid=uuid.UUID(SEED_GID),
            relationship_types=["producer", "performer"],
            min_paths=2,
            limit=20,
        )
        names = [r["artist_name"] for r in results]
        assert "Artist X" in names
        assert "Artist Z" in names
        assert "Artist Y" not in names

    def test_single_path_with_min_paths_1(self, seeded_session):
        repo = RecommendationRepository()
        results = repo.find_multi_path_artists(
            seeded_session,
            seed_mbid=uuid.UUID(SEED_GID),
            relationship_types=["producer", "performer"],
            min_paths=1,
            limit=20,
        )
        names = [r["artist_name"] for r in results]
        assert "Artist X" in names
        assert "Artist Y" in names
        assert "Artist Z" in names

    def test_filters_by_relationship_type(self, seeded_session):
        repo = RecommendationRepository()
        results = repo.find_multi_path_artists(
            seeded_session,
            seed_mbid=uuid.UUID(SEED_GID),
            relationship_types=["producer"],
            min_paths=1,
            limit=20,
        )
        names = [r["artist_name"] for r in results]
        assert "Artist X" in names
        assert "Artist Y" in names
        assert "Artist Z" in names

    def test_respects_limit(self, seeded_session):
        repo = RecommendationRepository()
        results = repo.find_multi_path_artists(
            seeded_session,
            seed_mbid=uuid.UUID(SEED_GID),
            relationship_types=["producer", "performer"],
            min_paths=1,
            limit=2,
        )
        assert len(results) <= 2

    def test_returns_path_details(self, seeded_session):
        repo = RecommendationRepository()
        results = repo.find_multi_path_artists(
            seeded_session,
            seed_mbid=uuid.UUID(SEED_GID),
            relationship_types=["producer", "performer"],
            min_paths=2,
            limit=20,
        )
        artist_x = [r for r in results if r["artist_name"] == "Artist X"][0]
        assert artist_x["path_count"] == 2
        path_types = {p["relationship_type"] for p in artist_x["paths"]}
        assert "producer" in path_types
        assert "performer" in path_types

    def test_excludes_seed_artist(self, seeded_session):
        repo = RecommendationRepository()
        results = repo.find_multi_path_artists(
            seeded_session,
            seed_mbid=uuid.UUID(SEED_GID),
            relationship_types=["producer", "performer"],
            min_paths=1,
            limit=20,
        )
        mbids = [r["artist_mbid"] for r in results]
        assert SEED_GID not in mbids

    def test_no_results_returns_empty(self, seeded_session):
        repo = RecommendationRepository()
        results = repo.find_multi_path_artists(
            seeded_session,
            seed_mbid=uuid.UUID("99999999-9999-9999-9999-999999999999"),
            relationship_types=["producer"],
            min_paths=1,
            limit=20,
        )
        assert results == []


class TestGetArtistByMbid:
    def test_found(self, seeded_session):
        repo = RecommendationRepository()
        result = repo.get_artist_by_mbid(seeded_session, uuid.UUID(SEED_GID))
        assert result is not None
        assert result["name"] == "Seed Artist"
        assert result["mbid"] == SEED_GID

    def test_not_found(self, seeded_session):
        repo = RecommendationRepository()
        result = repo.get_artist_by_mbid(
            seeded_session,
            uuid.UUID("99999999-9999-9999-9999-999999999999"),
        )
        assert result is None


class TestSeedExcludedFromCollaborators:
    def test_seed_not_in_via_paths(self, seeded_session):
        repo = RecommendationRepository()
        results = repo.find_multi_path_artists(
            seeded_session,
            seed_mbid=uuid.UUID(SEED_GID),
            relationship_types=["producer", "performer"],
            min_paths=1,
            limit=20,
        )
        for r in results:
            for p in r["paths"]:
                assert p["via"] != "Seed Artist"


class TestCollaboratorArtistCount:
    def test_paths_include_collaborator_artist_count(self, seeded_session):
        repo = RecommendationRepository()
        results = repo.find_multi_path_artists(
            seeded_session,
            seed_mbid=uuid.UUID(SEED_GID),
            relationship_types=["producer", "performer"],
            min_paths=1,
            limit=20,
        )
        for r in results:
            for p in r["paths"]:
                assert "collaborator_artist_count" in p
                assert isinstance(p["collaborator_artist_count"], int)
                assert p["collaborator_artist_count"] >= 1


class TestGetArtistTags:
    def test_returns_tags_for_known_artists(self, seeded_session):
        repo = RecommendationRepository()
        tags = repo.get_artist_tags(seeded_session, [SEED_GID, ARTIST_X_GID])
        assert SEED_GID in tags
        assert tags[SEED_GID]["indie rock"] == 9
        assert tags[SEED_GID]["noise pop"] == 5
        assert ARTIST_X_GID in tags
        assert tags[ARTIST_X_GID]["indie rock"] == 7

    def test_returns_empty_for_untagged_artist(self, seeded_session):
        repo = RecommendationRepository()
        tags = repo.get_artist_tags(seeded_session, [PRODUCER_GID])
        assert tags.get(PRODUCER_GID, {}) == {}

    def test_returns_empty_for_empty_list(self, seeded_session):
        repo = RecommendationRepository()
        tags = repo.get_artist_tags(seeded_session, [])
        assert tags == {}


class TestGetObviousRelatedMbids:
    def test_returns_band_members(self, seeded_session):
        repo = RecommendationRepository()
        # Artist Y (id=200) is "member of band" Seed (id=1)
        related = repo.get_obvious_related_mbids(seeded_session, uuid.UUID(SEED_GID))
        assert ARTIST_Y_GID in related

    def test_does_not_return_unrelated(self, seeded_session):
        repo = RecommendationRepository()
        related = repo.get_obvious_related_mbids(seeded_session, uuid.UUID(SEED_GID))
        # Artist X and Artist Z have no "member of band" relationship with Seed
        assert ARTIST_X_GID not in related
        assert ARTIST_Z_GID not in related

    def test_empty_for_no_relationships(self, seeded_session):
        repo = RecommendationRepository()
        related = repo.get_obvious_related_mbids(
            seeded_session, uuid.UUID(ARTIST_X_GID)
        )
        assert related == set()
