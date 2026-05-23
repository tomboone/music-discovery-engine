import re
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.repositories.mbid_resolution import MbidResolutionRepository

_DISCOGS_SUFFIX_RE = re.compile(r"\s*\(\d+\)\s*$")


def normalize_name(raw: str) -> str:
    """Strip Discogs' ``(N)`` disambiguation suffix and surrounding whitespace.

    Discogs distinguishes same-named artists within its own catalog by appending
    ``(N)`` (e.g., ``"Cream (2)"``). MusicBrainz uses a separate ``comment`` field
    for disambiguation, so the suffix must be removed before looking up an
    artist by name.
    """
    return _DISCOGS_SUFFIX_RE.sub("", raw).strip()


class MbidResolutionService:
    def __init__(self, repository: MbidResolutionRepository) -> None:
        self._repository = repository

    def run(
        self,
        app_session: Session,
        mb_session: Session,
        user_id: uuid.UUID,
    ) -> dict:
        names = self._repository.find_unresolved_artist_names(app_session, user_id)
        resolutions: dict[str, uuid.UUID] = {}

        for name in names:
            gid = self._repository.find_artist_gid(mb_session, normalize_name(name))
            if gid is not None:
                resolutions[name] = gid

        if resolutions:
            self._repository.update_artist_mbids(app_session, user_id, resolutions)
            app_session.commit()

        return {
            "attempted": len(names),
            "resolved": len(resolutions),
            "unmatched": len(names) - len(resolutions),
            "run_at": datetime.now(UTC).isoformat(),
        }
