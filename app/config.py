from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_db_url: str = (
        "postgresql+psycopg://root:root@tbc_postgresql_db:5432/music_discovery"
    )
    musicbrainz_db_url: str = (
        "postgresql+psycopg://root:root@tbc_postgresql_db:5432/musicbrainz"
    )
    lastfm_api_key: str = ""
    lastfm_shared_secret: str = ""
    lastfm_callback_url: str = (
        "https://music-discovery-api.localhost/auth/lastfm/callback"
    )
