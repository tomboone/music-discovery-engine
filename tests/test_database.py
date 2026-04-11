from unittest.mock import patch

from sqlalchemy import text

from app.database import (
    create_app_db,
    get_app_engine,
    get_app_session,
    get_mb_engine,
    get_mb_session,
)


def test_get_app_engine(settings):
    engine = get_app_engine(settings)
    assert "music_discovery" in str(engine.url)


def test_get_mb_engine(settings):
    engine = get_mb_engine(settings)
    assert "musicbrainz" in str(engine.url)


def test_get_app_session(settings):
    engine = get_app_engine(settings)
    gen = get_app_session(engine)
    session = next(gen)
    assert session is not None
    # cleanup
    try:
        next(gen)
    except StopIteration:
        pass


def test_get_mb_session(settings):
    engine = get_mb_engine(settings)
    gen = get_mb_session(engine)
    session = next(gen)
    assert session is not None
    try:
        next(gen)
    except StopIteration:
        pass


def test_create_app_db_runs_create_database(settings):
    with patch("app.database.create_engine") as mock_create_engine:
        mock_conn = mock_create_engine.return_value.connect.return_value.__enter__.return_value
        mock_conn.execute.return_value.scalar.return_value = None
        create_app_db(settings)
        mock_create_engine.assert_called_once()
        assert "root" in str(mock_create_engine.call_args)
