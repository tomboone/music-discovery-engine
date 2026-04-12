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
