import uuid
from unittest.mock import MagicMock

import pytest

from app.clients.discogs import DiscogsApiError, DiscogsAuthError
from app.services.discogs import DiscogsService


def test_begin_auth_persists_request_token_and_returns_url():
    mock_client = MagicMock()
    mock_client.get_request_token.return_value = ("rt_x", "rts_y")
    mock_client.get_authorize_url.return_value = (
        "https://example.com/authorize?oauth_token=rt_x"
    )
    mock_repo = MagicMock()
    session = MagicMock()
    user_id = uuid.uuid4()

    service = DiscogsService(mock_client, mock_repo, MagicMock())
    url = service.begin_auth(session, user_id)

    mock_repo.save_request_token.assert_called_once_with(
        session, user_id, "rt_x", "rts_y"
    )
    assert url == "https://example.com/authorize?oauth_token=rt_x"


def test_complete_auth_happy_path():
    mock_client = MagicMock()
    mock_client.exchange_access_token.return_value = ("at_x", "ats_y")
    mock_client.get_identity.return_value = "audiophilesasquatch"
    mock_repo = MagicMock()
    mock_profile = MagicMock()
    mock_profile.request_token = "rt_x"
    mock_profile.request_token_secret = "rts_y"
    mock_profile.user_id = uuid.uuid4()
    mock_repo.get_profile_by_request_token.return_value = mock_profile

    service = DiscogsService(mock_client, mock_repo, MagicMock())
    profile = service.complete_auth(MagicMock(), oauth_token="rt_x", oauth_verifier="v")

    mock_client.get_identity.assert_called_once_with("at_x", "ats_y")
    mock_repo.save_access_token.assert_called_once()
    assert profile == mock_repo.save_access_token.return_value


def test_complete_auth_unknown_token_raises():
    mock_repo = MagicMock()
    mock_repo.get_profile_by_request_token.return_value = None
    service = DiscogsService(MagicMock(), mock_repo, MagicMock())
    with pytest.raises(ValueError, match="unknown oauth_token"):
        service.complete_auth(MagicMock(), oauth_token="nope", oauth_verifier="v")


def test_complete_auth_exchange_failure_wipes_request_token():
    mock_client = MagicMock()
    mock_client.exchange_access_token.side_effect = DiscogsAuthError("bad verifier")
    mock_repo = MagicMock()
    mock_profile = MagicMock()
    mock_profile.user_id = uuid.uuid4()
    mock_repo.get_profile_by_request_token.return_value = mock_profile

    service = DiscogsService(mock_client, mock_repo, MagicMock())
    with pytest.raises(DiscogsAuthError):
        service.complete_auth(MagicMock(), oauth_token="rt", oauth_verifier="bad")

    # The request token was wiped on failure
    assert mock_profile.request_token is None
    assert mock_profile.request_token_secret is None


def test_sync_taste_profile_happy_path():
    mock_client = MagicMock()
    mock_repo = MagicMock()
    mock_profile = MagicMock()
    mock_profile.last_synced_at = None
    mock_repo.get_discogs_profile.return_value = mock_profile
    mock_ingester = MagicMock()
    mock_ingester.ingest.return_value = {"artists_count": 5, "albums_count": 2}

    service = DiscogsService(mock_client, mock_repo, mock_ingester)
    session = MagicMock()
    user_id = uuid.uuid4()
    result = service.sync_taste_profile(session, user_id)

    assert result["artists_count"] == 5
    assert result["albums_count"] == 2
    assert "synced_at" in result
    session.commit.assert_called_once()


def test_sync_taste_profile_clears_access_token_on_401():
    mock_client = MagicMock()
    mock_repo = MagicMock()
    mock_profile = MagicMock()
    mock_repo.get_discogs_profile.return_value = mock_profile
    mock_ingester = MagicMock()
    mock_ingester.ingest.side_effect = DiscogsApiError(401, "unauthorized")

    service = DiscogsService(mock_client, mock_repo, mock_ingester)
    session = MagicMock()
    with pytest.raises(DiscogsApiError):
        service.sync_taste_profile(session, uuid.uuid4())

    mock_repo.clear_access_token.assert_called_once()
    session.commit.assert_called_once()


def test_sync_taste_profile_429_rolls_back_and_reraises():
    mock_client = MagicMock()
    mock_repo = MagicMock()
    mock_ingester = MagicMock()
    mock_ingester.ingest.side_effect = DiscogsApiError(429, "rate limited")

    service = DiscogsService(mock_client, mock_repo, mock_ingester)
    session = MagicMock()

    with pytest.raises(DiscogsApiError) as exc_info:
        service.sync_taste_profile(session, uuid.uuid4())
    assert exc_info.value.status == 429

    session.rollback.assert_called_once()
    mock_repo.clear_access_token.assert_not_called()


def test_sync_taste_profile_generic_error_rolls_back_and_reraises():
    mock_client = MagicMock()
    mock_repo = MagicMock()
    mock_ingester = MagicMock()
    mock_ingester.ingest.side_effect = DiscogsApiError(503, "service unavailable")

    service = DiscogsService(mock_client, mock_repo, mock_ingester)
    session = MagicMock()

    with pytest.raises(DiscogsApiError) as exc_info:
        service.sync_taste_profile(session, uuid.uuid4())
    assert exc_info.value.status == 503

    session.rollback.assert_called_once()
    mock_repo.clear_access_token.assert_not_called()


def test_get_status_unlinked_returns_dict():
    mock_repo = MagicMock()
    mock_repo.get_discogs_profile.return_value = None

    service = DiscogsService(MagicMock(), mock_repo, MagicMock())
    result = service.get_status(MagicMock(), uuid.uuid4())

    assert result == {"linked": False}


def test_get_status_linked_returns_dict():
    from datetime import UTC, datetime

    mock_repo = MagicMock()
    mock_profile = MagicMock()
    mock_profile.access_token = "at_x"
    mock_profile.discogs_username = "audiophilesasquatch"
    mock_profile.last_synced_at = datetime(2026, 4, 18, 0, 0, tzinfo=UTC)
    mock_repo.get_discogs_profile.return_value = mock_profile

    service = DiscogsService(MagicMock(), mock_repo, MagicMock())
    result = service.get_status(MagicMock(), uuid.uuid4())

    assert result["linked"] is True
    assert result["username"] == "audiophilesasquatch"
    assert result["last_synced_at"].startswith("2026-04-18")
