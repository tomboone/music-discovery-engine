import pytest

from app.config import Settings


@pytest.fixture
def settings():
    return Settings()
