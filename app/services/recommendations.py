import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.lastfm import LastfmClient
from app.models.app import ArtistListenerCache, TasteProfileArtist
from app.repositories.recommendations import RecommendationRepository
from app.services.scoring import (
    compute_collaborator_diversity,
    compute_final_score,
    compute_genre_affinity,
    compute_obscurity,
)

DEFAULT_RELATIONSHIP_TYPES = ["producer", "instrument", "performer", "vocal"]
DEFAULT_WEIGHTS = {
    "path_count": 1.0,
    "genre_affinity": 0.5,
    "collaborator_diversity": 0.3,
    "obscurity": 0.5,
}
DEFAULT_MAX_LISTENERS = 2_000_000


class RecommendationService:
    def __init__(
        self,
        repository: RecommendationRepository,
        lastfm_client: LastfmClient | None = None,
    ) -> None:
        self._repository = repository
        self._lastfm_client = lastfm_client

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
        min_graph_results: int = 5,
        max_listeners: int = DEFAULT_MAX_LISTENERS,
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

        # Filter out obviously related artists (band members, alter egos, etc.)
        obvious_mbids = self._repository.get_obvious_related_mbids(
            mb_session, seed_mbid
        )
        raw_results = [r for r in raw_results if r["artist_mbid"] not in obvious_mbids]

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

        # Fetch listener counts — check cache first, then Last.fm API
        listener_counts: dict[str, int] = {}
        names_to_fetch = {r["artist_name"] for r in raw_results}

        if names_to_fetch and self._lastfm_client:
            # Load from cache (entries less than 30 days old)
            cutoff = datetime.now(UTC) - timedelta(days=30)
            cached = (
                app_session.execute(
                    select(ArtistListenerCache).where(
                        ArtistListenerCache.artist_name.in_(names_to_fetch),
                        ArtistListenerCache.fetched_at > cutoff,
                    )
                )
                .scalars()
                .all()
            )
            for c in cached:
                listener_counts[c.artist_name] = c.listeners
                names_to_fetch.discard(c.artist_name)

        # Fetch remaining from Last.fm API
        if names_to_fetch and self._lastfm_client:
            for name in names_to_fetch:
                try:
                    count = self._lastfm_client.get_artist_listeners(name)
                except Exception:
                    count = 0
                listener_counts[name] = count
                # Upsert to cache
                existing = app_session.execute(
                    select(ArtistListenerCache).where(
                        ArtistListenerCache.artist_name == name
                    )
                ).scalar_one_or_none()
                if existing:
                    existing.listeners = count
                    existing.fetched_at = datetime.now(UTC)
                else:
                    app_session.add(
                        ArtistListenerCache(
                            artist_name=name,
                            listeners=count,
                        )
                    )
            app_session.commit()

        # Filter by max_listeners hard ceiling
        if max_listeners > 0 and listener_counts:
            raw_results = [
                r
                for r in raw_results
                if listener_counts.get(r["artist_name"], 0) < max_listeners
            ]

        # Score each candidate
        scored = []
        for r in raw_results:
            candidate_tags = all_tags.get(r["artist_mbid"], {})
            genre_aff = compute_genre_affinity(seed_tags, candidate_tags)
            collab_div = compute_collaborator_diversity(
                r.get("paths", []), max_collab_count
            )
            listeners = listener_counts.get(r["artist_name"], 0)
            obscurity = compute_obscurity(listeners, max_listeners)
            final = compute_final_score(
                r["path_count"], genre_aff, collab_div, obscurity, weights
            )
            scored.append(
                {
                    **r,
                    "genre_affinity": genre_aff,
                    "collaborator_diversity": collab_div,
                    "obscurity": obscurity,
                    "listeners": listeners,
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
                        "obscurity": round(r["obscurity"], 4),
                        "listeners": r["listeners"],
                        "final_score": round(r["final_score"], 4),
                    },
                }
            )

        # Fallback: Last.fm similar artists
        fallback_recommendations: list[dict] = []
        fallback_reason: str | None = None

        if (
            min_graph_results > 0
            and len(recommendations) < min_graph_results
            and self._lastfm_client is not None
        ):
            try:
                similar = self._lastfm_client.get_similar_artists(seed_artist["name"])
            except Exception:
                similar = []

            graph_names = {r["artist"]["name"] for r in recommendations}

            for s in similar:
                # Filter known artists by MBID
                if s["mbid"]:
                    try:
                        s_mbid = uuid.UUID(s["mbid"])
                        if s_mbid in known_mbids:
                            continue
                    except (ValueError, TypeError):
                        pass
                # Filter duplicates with graph results by name
                if s["name"] in graph_names:
                    continue
                fallback_recommendations.append(
                    {
                        "artist": {
                            "name": s["name"],
                            "mbid": s["mbid"],
                        },
                        "match": s["match"],
                        "source": "lastfm_similar",
                    }
                )

            if fallback_recommendations:
                fallback_reason = "graph_results_below_threshold"

        return {
            "seed_artist": seed_artist,
            "recommendations": recommendations,
            "fallback_recommendations": fallback_recommendations,
            "fallback_reason": fallback_reason,
            "params": {
                "relationship_types": relationship_types,
                "min_paths": min_paths,
                "limit": limit,
                "weights": weights,
                "min_graph_results": min_graph_results,
                "max_listeners": max_listeners,
            },
            "filtered_known_artists": filtered_count,
        }
