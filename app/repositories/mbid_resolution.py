import uuid

from sqlalchemy import text, update
from sqlalchemy.orm import Session

from app.models.app import TasteProfileArtist


class MbidResolutionRepository:
    def find_unresolved_artist_names(
        self, app_session: Session, user_id: uuid.UUID
    ) -> list[str]:
        rows = (
            app_session.query(TasteProfileArtist.artist_name)
            .filter(
                TasteProfileArtist.user_id == user_id,
                TasteProfileArtist.artist_mbid.is_(None),
            )
            .distinct()
            .order_by(TasteProfileArtist.artist_name)
            .all()
        )
        return [name for (name,) in rows]

    def find_artist_gid(
        self, mb_session: Session, normalized_name: str
    ) -> uuid.UUID | None:
        rows = mb_session.execute(
            text(
                """
                SELECT gid
                FROM artist
                WHERE lower(musicbrainz_unaccent(name))
                      = lower(musicbrainz_unaccent(:name))
                  AND comment = ''
                LIMIT 2
                """
            ),
            {"name": normalized_name},
        ).all()
        if len(rows) != 1:
            return None
        gid_value = rows[0][0]
        if isinstance(gid_value, uuid.UUID):
            return gid_value
        return uuid.UUID(str(gid_value))

    def update_artist_mbids(
        self,
        app_session: Session,
        user_id: uuid.UUID,
        resolutions: dict[str, uuid.UUID],
    ) -> int:
        total = 0
        for name, gid in resolutions.items():
            result = app_session.execute(
                update(TasteProfileArtist)
                .where(
                    TasteProfileArtist.user_id == user_id,
                    TasteProfileArtist.artist_name == name,
                    TasteProfileArtist.artist_mbid.is_(None),
                )
                .values(artist_mbid=gid)
            )
            total += result.rowcount or 0  # pyright: ignore[reportAttributeAccessIssue]
        return total
