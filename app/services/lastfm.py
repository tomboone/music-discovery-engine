import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.clients.lastfm import LastfmClient
from app.models.app import LastfmProfile
from app.repositories.lastfm import LastfmRepository
from app.services.taste_profile import (
    AlbumEntry,
    ArtistEntry,
    TasteProfileSnapshot,
)
from app.services.taste_profile.ingester import TasteProfileIngester


class LastfmSource:
    def __init__(self, client: LastfmClient, repository: LastfmRepository) -> None:
        self._client = client
        self._repository = repository

    def fetch(self, session: Session, user_id: uuid.UUID) -> TasteProfileSnapshot:
        profile = self._repository.get_lastfm_profile(session, user_id)
        if not profile:
            raise ValueError("Last.fm account not linked")

        raw_artists = self._client.get_top_artists(
            profile.lastfm_username, period="overall"
        )
        raw_albums = self._client.get_top_albums(
            profile.lastfm_username, period="overall"
        )

        artists = [
            ArtistEntry(
                name=a["name"],
                mbid=a.get("mbid") or None,
                count=int(a["playcount"]),
            )
            for a in raw_artists
        ]
        albums = [
            AlbumEntry(
                name=al["name"],
                artist_name=al["artist"]["name"],
                mbid=al.get("mbid") or None,
                artist_mbid=al["artist"].get("mbid") or None,
                count=int(al["playcount"]),
            )
            for al in raw_albums
        ]

        return TasteProfileSnapshot(
            source="lastfm",
            artists_by_period={"overall": artists},
            albums_by_period={"overall": albums},
        )


class LastfmService:
    def __init__(
        self,
        client: LastfmClient,
        repository: LastfmRepository,
        ingester: TasteProfileIngester,
    ) -> None:
        self._client = client
        self._repository = repository
        self._ingester = ingester

    def complete_auth(
        self, session: Session, user_id: uuid.UUID, token: str
    ) -> LastfmProfile:
        session_key, username = self._client.exchange_token(token)
        return self._repository.save_lastfm_profile(
            session, user_id, username, session_key
        )

    def sync_taste_profile(self, session: Session, user_id: uuid.UUID) -> dict:
        source = LastfmSource(self._client, self._repository)
        result = self._ingester.ingest(session, user_id, source)

        profile = self._repository.get_lastfm_profile(session, user_id)
        assert profile is not None, "profile must exist after successful sync"
        synced_at = datetime.now(UTC)
        profile.last_synced_at = synced_at
        session.commit()

        return {
            "artists_count": result["artists_count"],
            "albums_count": result["albums_count"],
            "synced_at": synced_at.isoformat(),
        }
