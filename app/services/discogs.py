import uuid
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.clients.discogs import DiscogsApiError, DiscogsAuthError, DiscogsClient
from app.models.app import DiscogsProfile
from app.repositories.discogs import DiscogsRepository
from app.services.taste_profile import (
    AlbumEntry,
    ArtistEntry,
    TasteProfileSnapshot,
)
from app.services.taste_profile.ingester import TasteProfileIngester

VARIOUS_ARTIST_ID = 194

# Maps Discogs format descriptions to normalized release_type values. First
# match wins during scan of an item's formats[].descriptions. Items without a
# matching description fall back to "album".
RELEASE_TYPE_KEYWORDS = {
    "Single": "single",
    "EP": "ep",
    "Mini-Album": "ep",
    "Compilation": "compilation",
}


class DiscogsSource:
    def __init__(self, client: DiscogsClient, repository: DiscogsRepository) -> None:
        self._client = client
        self._repository = repository

    def fetch(self, session: Session, user_id: uuid.UUID) -> TasteProfileSnapshot:
        profile = self._repository.get_discogs_profile(session, user_id)
        if (
            profile is None
            or not profile.access_token
            or not profile.access_token_secret
            or not profile.discogs_username
        ):
            raise ValueError("Discogs account not linked")

        collection_items = self._client.get_collection(
            profile.discogs_username, profile.access_token, profile.access_token_secret
        )
        wantlist_items = self._client.get_wantlist(
            profile.discogs_username, profile.access_token, profile.access_token_secret
        )

        return TasteProfileSnapshot(
            source="discogs",
            artists_by_period={
                "collection": self._aggregate_artists(collection_items),
                "wantlist": self._aggregate_artists(wantlist_items),
            },
            albums_by_period={
                "collection": self._dedupe_albums(collection_items),
                "wantlist": self._dedupe_albums(wantlist_items),
            },
        )

    def _aggregate_artists(self, items: list[dict]) -> list[ArtistEntry]:
        counts: Counter[str] = Counter()
        for item in items:
            primary = self._primary_artist(item)
            if primary is None:
                continue
            counts[primary["name"]] += 1
        return [
            ArtistEntry(name=name, mbid=None, count=c) for name, c in counts.items()
        ]

    def _dedupe_albums(self, items: list[dict]) -> list[AlbumEntry]:
        # Dedup by (artist_name, title, release_type). Matches the DB unique
        # constraint on TasteProfileAlbum. Keeps album and single of the same
        # title distinct; collapses multiple pressings or duplicate masters
        # of the same (artist, title, type) into one row with summed count.
        buckets: dict[tuple, dict] = {}
        for item in items:
            basic = item.get("basic_information") or {}
            title = basic.get("title")
            primary = self._primary_artist(item)
            if not title or primary is None:
                continue
            release_type = self._derive_release_type(basic)
            key = (primary["name"], title, release_type)
            if key in buckets:
                buckets[key]["count"] += 1
            else:
                buckets[key] = {
                    "name": title,
                    "artist_name": primary["name"],
                    "release_type": release_type,
                    "count": 1,
                }
        return [
            AlbumEntry(
                name=b["name"],
                artist_name=b["artist_name"],
                mbid=None,
                artist_mbid=None,
                count=b["count"],
                release_type=b["release_type"],
            )
            for b in buckets.values()
        ]

    @staticmethod
    def _derive_release_type(basic: dict) -> str:
        for fmt in basic.get("formats") or []:
            for desc in fmt.get("descriptions") or []:
                if desc in RELEASE_TYPE_KEYWORDS:
                    return RELEASE_TYPE_KEYWORDS[desc]
        return "album"

    @staticmethod
    def _primary_artist(item: dict) -> dict | None:
        basic = item.get("basic_information") or {}
        artists = basic.get("artists") or []
        if not artists:
            return None
        primary = artists[0]
        if primary.get("id") == VARIOUS_ARTIST_ID:
            return None
        return primary


class DiscogsService:
    def __init__(
        self,
        client: DiscogsClient,
        repository: DiscogsRepository,
        ingester: TasteProfileIngester,
    ) -> None:
        self._client = client
        self._repository = repository
        self._ingester = ingester

    def begin_auth(self, session: Session, user_id: uuid.UUID) -> str:
        token, secret = self._client.get_request_token()
        self._repository.save_request_token(session, user_id, token, secret)
        return self._client.get_authorize_url(token)

    def complete_auth(
        self, session: Session, oauth_token: str, oauth_verifier: str
    ) -> DiscogsProfile:
        profile = self._repository.get_profile_by_request_token(session, oauth_token)
        if profile is None:
            raise ValueError("unknown oauth_token")
        if not profile.request_token or not profile.request_token_secret:
            raise ValueError("missing request token state")

        try:
            access_token, access_secret = self._client.exchange_access_token(
                profile.request_token, profile.request_token_secret, oauth_verifier
            )
        except DiscogsAuthError:
            profile.request_token = None
            profile.request_token_secret = None
            session.commit()
            raise

        username = self._client.get_identity(access_token, access_secret)
        return self._repository.save_access_token(
            session, profile.user_id, access_token, access_secret, username
        )

    def get_status(self, session: Session, user_id: uuid.UUID) -> dict:
        profile = self._repository.get_discogs_profile(session, user_id)
        if profile and profile.access_token:
            return {
                "linked": True,
                "username": profile.discogs_username,
                "last_synced_at": (
                    profile.last_synced_at.isoformat()
                    if profile.last_synced_at
                    else None
                ),
            }
        return {"linked": False}

    def sync_taste_profile(self, session: Session, user_id: uuid.UUID) -> dict:
        source = DiscogsSource(self._client, self._repository)
        try:
            result = self._ingester.ingest(session, user_id, source)
        except DiscogsApiError as e:
            session.rollback()
            if e.status == 401:
                self._repository.clear_access_token(session, user_id)
                session.commit()
            raise

        profile = self._repository.get_discogs_profile(session, user_id)
        assert profile is not None, "profile must exist after successful sync"
        synced_at = datetime.now(UTC)
        profile.last_synced_at = synced_at
        session.commit()

        return {
            "artists_count": result["artists_count"],
            "albums_count": result["albums_count"],
            "synced_at": synced_at.isoformat(),
        }
