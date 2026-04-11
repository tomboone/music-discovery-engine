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
    monkeypatch.setenv("MUSICBRAINZ_DB_URL", "postgresql+psycopg://test@localhost/test_mb")
    settings = Settings()
    assert settings.app_db_url == "postgresql+psycopg://test@localhost/test_app"
    assert settings.musicbrainz_db_url == "postgresql+psycopg://test@localhost/test_mb"
