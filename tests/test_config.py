from app.config import Settings


def test_default_app_db_url():
    settings = Settings()
    assert "music_discovery" in settings.app_db_url
    assert "psycopg" in settings.app_db_url


def test_default_musicbrainz_db_url():
    settings = Settings()
    assert "musicbrainz" in settings.musicbrainz_db_url
    assert "psycopg" in settings.musicbrainz_db_url


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("APP_DB_URL", "postgresql+psycopg://test@localhost/test_app")
    monkeypatch.setenv(
        "MUSICBRAINZ_DB_URL", "postgresql+psycopg://test@localhost/test_mb"
    )
    settings = Settings()
    assert settings.app_db_url == "postgresql+psycopg://test@localhost/test_app"
    assert settings.musicbrainz_db_url == "postgresql+psycopg://test@localhost/test_mb"


def test_lastfm_settings_defaults():
    settings = Settings()
    assert settings.lastfm_api_key == "" or isinstance(settings.lastfm_api_key, str)
    assert settings.lastfm_callback_url == (
        "https://music-discovery-api.localhost/auth/lastfm/callback"
    )


def test_lastfm_settings_from_env(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "test_key_123")
    monkeypatch.setenv("LASTFM_SHARED_SECRET", "test_secret_456")
    monkeypatch.setenv("LASTFM_CALLBACK_URL", "http://localhost/callback")
    settings = Settings()
    assert settings.lastfm_api_key == "test_key_123"
    assert settings.lastfm_shared_secret == "test_secret_456"
    assert settings.lastfm_callback_url == "http://localhost/callback"


def test_settings_have_discogs_fields():
    from app.config import Settings

    settings = Settings()
    assert hasattr(settings, "discogs_consumer_key")
    assert hasattr(settings, "discogs_consumer_secret")
    assert hasattr(settings, "discogs_callback_url")
    assert hasattr(settings, "discogs_user_agent")
    assert settings.discogs_callback_url == (
        "https://music-discovery-api.localhost/auth/discogs/callback"
    )
    assert settings.discogs_user_agent.startswith("MusicDiscoveryEngine/")
