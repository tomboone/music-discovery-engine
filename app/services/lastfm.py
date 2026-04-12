import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.clients.lastfm import LastfmClient
from app.models.app import LastfmProfile
from app.repositories.lastfm import LastfmRepository


class LastfmService:
    def __init__(self, client: LastfmClient, repository: LastfmRepository) -> None:
        self._client = client
        self._repository = repository

    def complete_auth(
        self, session: Session, user_id: uuid.UUID, token: str
    ) -> LastfmProfile:
        session_key, username = self._client.exchange_token(token)
        return self._repository.save_lastfm_profile(
            session, user_id, username, session_key
        )

    def sync_taste_profile(
        self, session: Session, user_id: uuid.UUID
    ) -> dict:
        profile = self._repository.get_lastfm_profile(session, user_id)
        if not profile:
            raise ValueError("Last.fm account not linked")

        artists = self._client.get_top_artists(
            profile.lastfm_username, period="overall"
        )
        albums = self._client.get_top_albums(
            profile.lastfm_username, period="overall"
        )

        self._repository.upsert_top_artists(
            session, user_id, "lastfm", "overall", artists
        )
        self._repository.upsert_top_albums(
            session, user_id, "lastfm", "overall", albums
        )

        profile.last_synced_at = datetime.now(timezone.utc)
        session.commit()

        return {
            "artists_count": len(artists),
            "albums_count": len(albums),
            "synced_at": profile.last_synced_at.isoformat(),
        }
