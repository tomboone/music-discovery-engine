import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.app import TasteProfileArtist
from app.repositories.generation import GenerationRepository
from app.services.recommendations import RecommendationService
from app.services.seed_selection import select_seeds


class GenerationService:
    def __init__(
        self,
        recommendation_service: RecommendationService,
        repository: GenerationRepository,
    ) -> None:
        self._rec_service = recommendation_service
        self._repository = repository

    def generate(
        self,
        mb_session: Session,
        app_session: Session,
        user_id: uuid.UUID,
        num_seeds: int = 3,
        num_also_explore: int = 3,
    ) -> dict:
        # 1. Load taste profile
        taste_rows = (
            app_session.execute(
                select(TasteProfileArtist)
                .where(TasteProfileArtist.user_id == user_id)
                .order_by(TasteProfileArtist.count.desc())
            )
            .scalars()
            .all()
        )

        if not taste_rows:
            return {"error": "no_taste_profile"}

        # 2. Convert to dicts for select_seeds
        taste_dicts = [
            {
                "artist_name": row.artist_name,
                "artist_mbid": str(row.artist_mbid) if row.artist_mbid else None,
                "count": row.count,
            }
            for row in taste_rows
        ]

        # 3. Select seeds
        seeds = select_seeds(taste_dicts, num_seeds)

        # 4. Fan out recommendations for each seed
        all_recs = []
        for seed in seeds:
            try:
                result = self._rec_service.get_recommendations(
                    mb_session=mb_session,
                    app_session=app_session,
                    seed_mbid=uuid.UUID(seed["artist_mbid"]),
                    user_id=user_id,
                )
            except (ValueError, TypeError):
                continue

            if result is None:
                continue

            seed_artist = result.get("seed_artist", {})

            # Collect graph recommendations
            for rec in result.get("recommendations", []):
                rec_copy = dict(rec)
                rec_copy["seed_artist"] = seed_artist
                rec_copy["source"] = "graph"
                rec_copy["_sort_score"] = rec.get("score", {}).get("final_score", 0)
                all_recs.append(rec_copy)

            # Collect fallback recommendations
            for rec in result.get("fallback_recommendations", []):
                rec_copy = dict(rec)
                rec_copy["seed_artist"] = seed_artist
                rec_copy["source"] = "lastfm_similar"
                rec_copy["_sort_score"] = rec.get("match", 0)
                all_recs.append(rec_copy)

        # 5. Deduplicate by MBID (or name: key), keeping highest score
        deduped = {}
        for rec in all_recs:
            artist = rec.get("artist", {})
            mbid = artist.get("mbid")
            key = str(mbid) if mbid else f"name:{artist.get('name', '')}"

            if key not in deduped or rec["_sort_score"] > deduped[key]["_sort_score"]:
                deduped[key] = rec

        # 6. Sort by score descending
        candidates = sorted(
            deduped.values(), key=lambda r: r["_sort_score"], reverse=True
        )

        # 7. Filter against history
        total_candidates = len(candidates)
        history = self._repository.get_recent_history(app_session, user_id)
        candidates = [r for r in candidates if self._rec_key(r) not in history]
        filtered_by_history = total_candidates - len(candidates)

        # 8. Pick primary + also-explore
        primary = None
        also_explore = []

        if candidates:
            primary = candidates[0]
            remaining = candidates[1:]

            if num_also_explore > 0 and remaining:
                primary_seed = self._seed_key(primary)
                # Prefer different seeds first
                diff_seed = [r for r in remaining if self._seed_key(r) != primary_seed]
                same_seed = [r for r in remaining if self._seed_key(r) == primary_seed]

                for r in diff_seed:
                    if len(also_explore) >= num_also_explore:
                        break
                    also_explore.append(r)

                for r in same_seed:
                    if len(also_explore) >= num_also_explore:
                        break
                    also_explore.append(r)

        # 9. Persist to history
        history_records = []
        if primary:
            history_records.append(self._to_history_record(primary, "primary"))
        for rec in also_explore:
            history_records.append(self._to_history_record(rec, "also_explore"))

        if history_records:
            self._repository.save_recommendations(app_session, user_id, history_records)

        # 10. Return result
        return {
            "primary": self._clean(primary) if primary else None,
            "also_explore": [self._clean(r) for r in also_explore],
            "metadata": {
                "seeds_used": [
                    {"name": s["artist_name"], "mbid": s["artist_mbid"]} for s in seeds
                ],
                "total_candidates": total_candidates,
                "filtered_by_history": filtered_by_history,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        }

    @staticmethod
    def _rec_key(rec: dict) -> str:
        artist = rec.get("artist", {})
        mbid = artist.get("mbid")
        if mbid:
            return str(mbid)
        return f"name:{artist.get('name', '')}"

    @staticmethod
    def _seed_key(rec: dict) -> str:
        seed = rec.get("seed_artist", {})
        mbid = seed.get("mbid")
        if mbid:
            return str(mbid)
        return f"name:{seed.get('name', '')}"

    @staticmethod
    def _clean(rec: dict) -> dict:
        cleaned = {k: v for k, v in rec.items() if not k.startswith("_")}
        return cleaned

    @staticmethod
    def _to_history_record(rec: dict, rec_type: str) -> dict:
        artist = rec.get("artist", {})
        seed = rec.get("seed_artist", {})
        return {
            "artist_name": artist.get("name"),
            "artist_mbid": artist.get("mbid"),
            "seed_artist_name": seed.get("name"),
            "seed_artist_mbid": seed.get("mbid"),
            "source": rec.get("source", "unknown"),
            "recommendation_type": rec_type,
            "score": rec.get("_sort_score"),
        }
