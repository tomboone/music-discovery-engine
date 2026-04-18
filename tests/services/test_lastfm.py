import uuid
from unittest.mock import MagicMock

import pytest

from app.clients.lastfm import LastfmAuthError
from app.models.app import LastfmProfile
from app.services.lastfm import LastfmService


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_ingester():
    return MagicMock()


@pytest.fixture
def service(mock_client, mock_repo, mock_ingester):
    return LastfmService(
        client=mock_client, repository=mock_repo, ingester=mock_ingester
    )


class TestCompleteAuth:
    def test_exchanges_token_and_saves_profile(self, service, mock_client, mock_repo):
        mock_client.exchange_token.return_value = ("session_key_123", "testuser")
        mock_repo.save_lastfm_profile.return_value = LastfmProfile(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            lastfm_username="testuser",
            session_key="session_key_123",
        )
        session = MagicMock()
        user_id = uuid.uuid4()

        result = service.complete_auth(session, user_id, "valid_token")

        mock_client.exchange_token.assert_called_once_with("valid_token")
        mock_repo.save_lastfm_profile.assert_called_once_with(
            session, user_id, "testuser", "session_key_123"
        )
        assert result.lastfm_username == "testuser"

    def test_propagates_auth_error(self, service, mock_client):
        mock_client.exchange_token.side_effect = LastfmAuthError("bad token")
        session = MagicMock()

        with pytest.raises(LastfmAuthError, match="bad token"):
            service.complete_auth(session, uuid.uuid4(), "bad_token")


class TestSyncTasteProfile:
    def test_calls_ingester_and_updates_synced_at(
        self, service, mock_client, mock_repo, mock_ingester
    ):
        user_id = uuid.uuid4()
        profile = LastfmProfile(
            id=uuid.uuid4(),
            user_id=user_id,
            lastfm_username="testuser",
            session_key="key",
        )
        mock_repo.get_lastfm_profile.return_value = profile
        mock_ingester.ingest.return_value = {
            "source": "lastfm",
            "artists_count": 1,
            "albums_count": 1,
        }
        session = MagicMock()

        result = service.sync_taste_profile(session, user_id)

        mock_ingester.ingest.assert_called_once()
        assert result["artists_count"] == 1
        assert result["albums_count"] == 1
        assert "synced_at" in result
        assert profile.last_synced_at is not None

    def test_raises_when_no_profile(self, service, mock_repo, mock_ingester):
        # LastfmSource.fetch raises ValueError when profile is missing; the
        # ingester bubbles that up unchanged.
        mock_ingester.ingest.side_effect = ValueError("Last.fm account not linked")
        session = MagicMock()

        with pytest.raises(ValueError, match="Last.fm account not linked"):
            service.sync_taste_profile(session, uuid.uuid4())
