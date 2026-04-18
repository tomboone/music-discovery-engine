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
    discogs_consumer_key: str = ""
    discogs_consumer_secret: str = ""
    discogs_callback_url: str = (
        "https://music-discovery-api.localhost/auth/discogs/callback"
    )
    discogs_user_agent: str = (
        "MusicDiscoveryEngine/0.1 +https://music-discovery-api.localhost"
    )
