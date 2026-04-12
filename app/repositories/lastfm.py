import uuid

from sqlalchemy.orm import Session

from app.models.app import LastfmProfile, TasteProfileAlbum, TasteProfileArtist


def _parse_mbid(mbid_str: str) -> uuid.UUID | None:
    if not mbid_str:
        return None
    try:
        return uuid.UUID(mbid_str)
    except ValueError:
        return None


class LastfmRepository:
    def save_lastfm_profile(
        self,
        session: Session,
        user_id: uuid.UUID,
        username: str,
        session_key: str,
    ) -> LastfmProfile:
        profile = (
            session.query(LastfmProfile).filter_by(user_id=user_id).first()
        )
        if profile:
            profile.lastfm_username = username
            profile.session_key = session_key
        else:
            profile = LastfmProfile(
                id=uuid.uuid4(),
                user_id=user_id,
                lastfm_username=username,
                session_key=session_key,
            )
            session.add(profile)
        session.commit()
        return profile

    def get_lastfm_profile(
        self, session: Session, user_id: uuid.UUID
    ) -> LastfmProfile | None:
        return session.query(LastfmProfile).filter_by(user_id=user_id).first()

    def upsert_top_artists(
        self,
        session: Session,
        user_id: uuid.UUID,
        source: str,
        period: str,
        artists: list[dict],
    ) -> None:
        incoming_names = set()
        for artist in artists:
            name = artist["name"]
            incoming_names.add(name)
            existing = (
                session.query(TasteProfileArtist)
                .filter_by(user_id=user_id, source=source, period=period, artist_name=name)
                .first()
            )
            if existing:
                existing.playcount = int(artist["playcount"])
                existing.rank = int(artist["@attr"]["rank"])
                existing.artist_mbid = _parse_mbid(artist.get("mbid", ""))
            else:
                session.add(
                    TasteProfileArtist(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        source=source,
                        period=period,
                        artist_name=name,
                        artist_mbid=_parse_mbid(artist.get("mbid", "")),
                        playcount=int(artist["playcount"]),
                        rank=int(artist["@attr"]["rank"]),
                    )
                )

        # Delete stale entries
        session.query(TasteProfileArtist).filter(
            TasteProfileArtist.user_id == user_id,
            TasteProfileArtist.source == source,
            TasteProfileArtist.period == period,
            ~TasteProfileArtist.artist_name.in_(incoming_names),
        ).delete(synchronize_session="fetch")

        session.commit()

    def upsert_top_albums(
        self,
        session: Session,
        user_id: uuid.UUID,
        source: str,
        period: str,
        albums: list[dict],
    ) -> None:
        incoming_keys = set()
        for album in albums:
            album_name = album["name"]
            artist_name = album["artist"]["name"]
            incoming_keys.add((album_name, artist_name))
            existing = (
                session.query(TasteProfileAlbum)
                .filter_by(
                    user_id=user_id,
                    source=source,
                    period=period,
                    album_name=album_name,
                    artist_name=artist_name,
                )
                .first()
            )
            if existing:
                existing.playcount = int(album["playcount"])
                existing.rank = int(album["@attr"]["rank"])
                existing.album_mbid = _parse_mbid(album.get("mbid", ""))
                existing.artist_mbid = _parse_mbid(album["artist"].get("mbid", ""))
            else:
                session.add(
                    TasteProfileAlbum(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        source=source,
                        period=period,
                        album_name=album_name,
                        album_mbid=_parse_mbid(album.get("mbid", "")),
                        artist_name=artist_name,
                        artist_mbid=_parse_mbid(album["artist"].get("mbid", "")),
                        playcount=int(album["playcount"]),
                        rank=int(album["@attr"]["rank"]),
                    )
                )

        # Delete stale entries
        all_existing = (
            session.query(TasteProfileAlbum)
            .filter_by(user_id=user_id, source=source, period=period)
            .all()
        )
        for existing in all_existing:
            if (existing.album_name, existing.artist_name) not in incoming_keys:
                session.delete(existing)

        session.commit()
