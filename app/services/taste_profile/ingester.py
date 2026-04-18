import uuid

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.app import TasteProfileAlbum, TasteProfileArtist
from app.services.taste_profile import (
    AlbumEntry,
    ArtistEntry,
    TasteProfileSource,
)


def _parse_mbid(mbid_str: str | None) -> uuid.UUID | None:
    if not mbid_str:
        return None
    try:
        return uuid.UUID(mbid_str)
    except ValueError:
        return None


class TasteProfileIngester:
    def ingest(
        self,
        session: Session,
        user_id: uuid.UUID,
        source: TasteProfileSource,
    ) -> dict:
        snapshot = source.fetch(session, user_id)

        artists_count = 0
        for period, entries in snapshot.artists_by_period.items():
            self._replace_artists(session, user_id, snapshot.source, period, entries)
            artists_count += len(entries)

        albums_count = 0
        for period, entries in snapshot.albums_by_period.items():
            self._replace_albums(session, user_id, snapshot.source, period, entries)
            albums_count += len(entries)

        return {
            "source": snapshot.source,
            "artists_count": artists_count,
            "albums_count": albums_count,
        }

    @staticmethod
    def _replace_artists(
        session: Session,
        user_id: uuid.UUID,
        source: str,
        period: str,
        entries: list[ArtistEntry],
    ) -> None:
        session.execute(
            delete(TasteProfileArtist).where(
                TasteProfileArtist.user_id == user_id,
                TasteProfileArtist.source == source,
                TasteProfileArtist.period == period,
            )
        )
        sorted_entries = sorted(entries, key=lambda e: e.count, reverse=True)
        for rank, entry in enumerate(sorted_entries, start=1):
            session.add(
                TasteProfileArtist(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    source=source,
                    period=period,
                    artist_name=entry.name,
                    artist_mbid=_parse_mbid(entry.mbid),
                    count=entry.count,
                    rank=rank,
                )
            )
        session.flush()

    @staticmethod
    def _replace_albums(
        session: Session,
        user_id: uuid.UUID,
        source: str,
        period: str,
        entries: list[AlbumEntry],
    ) -> None:
        session.execute(
            delete(TasteProfileAlbum).where(
                TasteProfileAlbum.user_id == user_id,
                TasteProfileAlbum.source == source,
                TasteProfileAlbum.period == period,
            )
        )
        sorted_entries = sorted(entries, key=lambda e: e.count, reverse=True)
        for rank, entry in enumerate(sorted_entries, start=1):
            session.add(
                TasteProfileAlbum(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    source=source,
                    period=period,
                    album_name=entry.name,
                    album_mbid=_parse_mbid(entry.mbid),
                    artist_name=entry.artist_name,
                    artist_mbid=_parse_mbid(entry.artist_mbid),
                    release_type=entry.release_type,
                    count=entry.count,
                    rank=rank,
                )
            )
        session.flush()
