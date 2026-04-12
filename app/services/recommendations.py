import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.app import TasteProfileArtist
from app.repositories.recommendations import RecommendationRepository
from app.services.scoring import (
    compute_collaborator_diversity,
    compute_final_score,
    compute_genre_affinity,
)

DEFAULT_RELATIONSHIP_TYPES = ["producer", "instrument", "performer", "vocal"]
DEFAULT_WEIGHTS = {
    "path_count": 1.0,
    "genre_affinity": 0.5,
    "collaborator_diversity": 0.3,
}


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
        weights: dict[str, float] | None = None,
    ) -> dict | None:
        if relationship_types is None:
            relationship_types = DEFAULT_RELATIONSHIP_TYPES
        if weights is None:
            weights = DEFAULT_WEIGHTS

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

        # Batch-fetch tags for seed + all candidates
        candidate_mbids = [r["artist_mbid"] for r in raw_results]
        all_mbids = [str(seed_mbid)] + candidate_mbids
        all_tags = self._repository.get_artist_tags(mb_session, all_mbids)
        seed_tags = all_tags.get(str(seed_mbid), {})

        # Find max collaborator_artist_count for normalization
        max_collab_count = 1
        for r in raw_results:
            for p in r.get("paths", []):
                count = p.get("collaborator_artist_count", 1)
                if count > max_collab_count:
                    max_collab_count = count

        # Score each candidate
        scored = []
        for r in raw_results:
            candidate_tags = all_tags.get(r["artist_mbid"], {})
            genre_aff = compute_genre_affinity(seed_tags, candidate_tags)
            collab_div = compute_collaborator_diversity(
                r.get("paths", []), max_collab_count
            )
            final = compute_final_score(r["path_count"], genre_aff, collab_div, weights)
            scored.append(
                {
                    **r,
                    "genre_affinity": genre_aff,
                    "collaborator_diversity": collab_div,
                    "final_score": final,
                }
            )

        # Sort by final score descending
        scored.sort(key=lambda x: x["final_score"], reverse=True)

        # Filter known artists
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
        for r in scored:
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
                    "score": {
                        "path_count": r["path_count"],
                        "genre_affinity": round(r["genre_affinity"], 4),
                        "collaborator_diversity": round(r["collaborator_diversity"], 4),
                        "final_score": round(r["final_score"], 4),
                    },
                }
            )

        return {
            "seed_artist": seed_artist,
            "recommendations": recommendations,
            "params": {
                "relationship_types": relationship_types,
                "min_paths": min_paths,
                "limit": limit,
                "weights": weights,
            },
            "filtered_known_artists": filtered_count,
        }
