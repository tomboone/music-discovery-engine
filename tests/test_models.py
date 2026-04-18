import uuid

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.models.app import Base, User


def test_user_table_schema():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("users")}
    assert columns == {"id", "email", "display_name", "created_at", "updated_at"}


def test_user_creation():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(id=uuid.uuid4(), email="test@example.com", display_name="Test")
        session.add(user)
        session.commit()
        result = session.get(User, user.id)
        assert result is not None
        assert result.email == "test@example.com"
        assert result.display_name == "Test"


def test_user_email_required():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(id=uuid.uuid4())
        session.add(user)
        try:
            session.commit()
            raise AssertionError("Should have raised")
        except Exception:
            session.rollback()


def test_discogs_profile_round_trip():
    import uuid as _uuid

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.models.app import Base, DiscogsProfile, User

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as s:
        user = User(id=_uuid.uuid4(), email="t@example.com", display_name="T")
        s.add(user)
        s.flush()

        profile = DiscogsProfile(
            id=_uuid.uuid4(),
            user_id=user.id,
            discogs_username=None,
            request_token="rt_x",
            request_token_secret="rts_y",
            access_token=None,
            access_token_secret=None,
        )
        s.add(profile)
        s.commit()

        loaded = s.query(DiscogsProfile).filter_by(user_id=user.id).one()
        assert loaded.request_token == "rt_x"
        assert loaded.request_token_secret == "rts_y"
        assert loaded.access_token is None
        assert loaded.discogs_username is None
        assert loaded.last_synced_at is None
