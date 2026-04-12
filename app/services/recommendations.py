import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.app import TasteProfileArtist
from app.repositories.recommendations import RecommendationRepository

DEFAULT_RELATIONSHIP_TYPES = ["producer", "instrument", "performer", "vocal"]


class RecommendationService:
    def __init__(self, repository: RecommendationRepository) -> None:
        self._repository = repository

    def get_recommendations(
        self,
        mb_session: Session,
        app_session: Session,
        seed_mbid: uuid.UUID,
        user_id: uuid.UUID,
        relationship_types: list[str] | None = None,
        min_paths: int = 2,
        limit: int = 20,
    ) -> dict | None:
        if relationship_types is None:
            relationship_types = DEFAULT_RELATIONSHIP_TYPES

        seed_artist = self._repository.get_artist_by_mbid(mb_session, seed_mbid)
        if seed_artist is None:
            return None

        raw_results = self._repository.find_multi_path_artists(
            mb_session,
            seed_mbid=seed_mbid,
            relationship_types=relationship_types,
            min_paths=min_paths,
            limit=limit + 50,
        )

        known_mbids = set(
            app_session.execute(
                select(TasteProfileArtist.artist_mbid).where(
                    TasteProfileArtist.user_id == user_id,
                    TasteProfileArtist.artist_mbid.is_not(None),
                )
            )
            .scalars()
            .all()
        )

        recommendations = []
        filtered_count = 0
        for r in raw_results:
            try:
                result_mbid = uuid.UUID(r["artist_mbid"])
            except (ValueError, TypeError):
                continue
            if result_mbid in known_mbids:
                filtered_count += 1
                continue
            if len(recommendations) >= limit:
                break
            recommendations.append(
                {
                    "artist": {
                        "name": r["artist_name"],
                        "mbid": r["artist_mbid"],
                    },
                    "path_count": r["path_count"],
                    "paths": r["paths"],
                }
            )

        return {
            "seed_artist": seed_artist,
            "recommendations": recommendations,
            "params": {
                "relationship_types": relationship_types,
                "min_paths": min_paths,
                "limit": limit,
            },
            "filtered_known_artists": filtered_count,
        }
