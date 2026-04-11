from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_db_url: str = (
        "postgresql+psycopg://root:root@tbc_postgresql_db:5432/music_discovery"
    )
    musicbrainz_db_url: str = (
        "postgresql+psycopg://root:root@tbc_postgresql_db:5432/musicbrainz"
    )
