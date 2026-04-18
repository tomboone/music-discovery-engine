import uuid
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session


@dataclass
class ArtistEntry:
    name: str
    mbid: str | None
    count: int


@dataclass
class AlbumEntry:
    name: str
    artist_name: str
    mbid: str | None
    artist_mbid: str | None
    count: int
    release_type: str = "album"


@dataclass
class TasteProfileSnapshot:
    source: str
    artists_by_period: dict[str, list[ArtistEntry]]
    albums_by_period: dict[str, list[AlbumEntry]]


class TasteProfileSource(Protocol):
    def fetch(self, session: Session, user_id: uuid.UUID) -> TasteProfileSnapshot: ...
