import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.app import RecommendationHistory


class GenerationRepository:
    def save_recommendations(
        self,
        session: Session,
        user_id: uuid.UUID,
        recommendations: list[dict],
    ) -> None:
        for rec in recommendations:
            mbid = rec.get("artist_mbid")
            if mbid and isinstance(mbid, str):
                try:
                    mbid = uuid.UUID(mbid)
                except (ValueError, TypeError):
                    mbid = None
            elif not mbid:
                mbid = None

            seed_mbid = rec.get("seed_artist_mbid")
            if seed_mbid and isinstance(seed_mbid, str):
                try:
                    seed_mbid = uuid.UUID(seed_mbid)
                except (ValueError, TypeError):
                    seed_mbid = None
            elif not seed_mbid:
                seed_mbid = None

            session.add(
                RecommendationHistory(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    artist_name=rec["artist_name"],
                    artist_mbid=mbid,
                    seed_artist_name=rec["seed_artist_name"],
                    seed_artist_mbid=seed_mbid,
                    source=rec["source"],
                    recommendation_type=rec["recommendation_type"],
                    score=rec.get("score"),
                )
            )
        session.commit()

    def get_recent_history(
        self,
        session: Session,
        user_id: uuid.UUID,
        months: int = 6,
    ) -> set[str]:
        cutoff = datetime.now(UTC) - timedelta(days=months * 30)
        rows = session.execute(
            select(
                RecommendationHistory.artist_mbid,
                RecommendationHistory.artist_name,
            ).where(
                RecommendationHistory.user_id == user_id,
                RecommendationHistory.created_at > cutoff,
            )
        ).all()
        result: set[str] = set()
        for row in rows:
            if row[0] is not None:
                result.add(str(row[0]))
            else:
                result.add(f"name:{row[1]}")
        return result
