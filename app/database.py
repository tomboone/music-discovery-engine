from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings


def get_app_engine(settings: Settings) -> Engine:
    return create_engine(settings.app_db_url, pool_pre_ping=True)


def get_mb_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.musicbrainz_db_url,
        pool_pre_ping=True,
        connect_args={"options": "-c search_path=musicbrainz,public"},
    )


def get_app_session(engine: Engine) -> Generator[Session]:
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_mb_session(engine: Engine) -> Generator[Session]:
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def create_app_db(settings: Settings) -> None:
    base_url = settings.app_db_url.rsplit("/", 1)[0] + "/root"
    engine = create_engine(base_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'music_discovery'")
        )
        if not result.scalar():
            conn.execute(text("CREATE DATABASE music_discovery"))
    engine.dispose()
