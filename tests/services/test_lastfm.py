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
def service(mock_client, mock_repo):
    return LastfmService(client=mock_client, repository=mock_repo)


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
    def test_fetches_and_upserts_data(self, service, mock_client, mock_repo):
        user_id = uuid.uuid4()
        profile = LastfmProfile(
            id=uuid.uuid4(),
            user_id=user_id,
            lastfm_username="testuser",
            session_key="key",
        )
        mock_repo.get_lastfm_profile.return_value = profile
        mock_client.get_top_artists.return_value = [
            {"name": "Artist1", "mbid": "", "playcount": "100", "@attr": {"rank": "1"}}
        ]
        mock_client.get_top_albums.return_value = [
            {
                "name": "Album1",
                "mbid": "",
                "playcount": "50",
                "artist": {"name": "Artist1", "mbid": ""},
                "@attr": {"rank": "1"},
            }
        ]
        session = MagicMock()

        result = service.sync_taste_profile(session, user_id)

        mock_client.get_top_artists.assert_called_once_with(
            "testuser", period="overall"
        )
        mock_client.get_top_albums.assert_called_once_with("testuser", period="overall")
        mock_repo.upsert_top_artists.assert_called_once()
        mock_repo.upsert_top_albums.assert_called_once()
        assert result["artists_count"] == 1
        assert result["albums_count"] == 1

    def test_raises_when_no_profile(self, service, mock_repo):
        mock_repo.get_lastfm_profile.return_value = None
        session = MagicMock()

        with pytest.raises(ValueError, match="Last.fm account not linked"):
            service.sync_taste_profile(session, uuid.uuid4())
