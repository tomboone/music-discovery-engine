import hashlib
from unittest.mock import patch

import httpx
import pytest

from app.clients.lastfm import LastfmApiError, LastfmAuthError, LastfmClient


@pytest.fixture
def client():
    return LastfmClient(
        api_key="test_api_key",
        shared_secret="test_secret",
        callback_url="http://localhost/callback",
    )


class TestGetAuthUrl:
    def test_returns_correct_url(self, client):
        url = client.get_auth_url()
        assert "https://www.last.fm/api/auth/" in url
        assert "api_key=test_api_key" in url
        assert (
            "cb=http%3A//localhost/callback" in url
            or "cb=http://localhost/callback" in url
            or "cb=http%3A%2F%2Flocalhost%2Fcallback" in url
        )


class TestSignature:
    def test_signature_generation(self, client):
        params = {
            "method": "auth.getSession",
            "api_key": "test_api_key",
            "token": "abc",
        }
        sig = client._build_signature(params)
        expected_input = (
            "api_keytest_api_keymethodauth.getSessiontokenabc" + "test_secret"
        )
        expected = hashlib.md5(expected_input.encode()).hexdigest()
        assert sig == expected

    def test_signature_excludes_format(self, client):
        params = {
            "method": "auth.getSession",
            "api_key": "key",
            "token": "t",
            "format": "json",
        }
        sig = client._build_signature(params)
        no_format = {"method": "auth.getSession", "api_key": "key", "token": "t"}
        sig_without = client._build_signature(no_format)
        assert sig == sig_without


class TestExchangeToken:
    def test_successful_exchange(self, client):
        mock_response = httpx.Response(
            200,
            json={
                "session": {
                    "name": "testuser",
                    "key": "session_key_123",
                    "subscriber": 0,
                }
            },
            request=httpx.Request("GET", "https://example.com"),
        )
        with patch.object(client._http, "get", return_value=mock_response):
            session_key, username = client.exchange_token("valid_token")
            assert session_key == "session_key_123"
            assert username == "testuser"

    def test_failed_exchange_raises_auth_error(self, client):
        mock_response = httpx.Response(
            200,
            json={"error": 4, "message": "Unauthorized Token"},
            request=httpx.Request("GET", "https://example.com"),
        )
        with (
            patch.object(client._http, "get", return_value=mock_response),
            pytest.raises(LastfmAuthError, match="Unauthorized Token"),
        ):
            client.exchange_token("bad_token")


class TestGetTopArtists:
    def test_single_page(self, client):
        mock_response = httpx.Response(
            200,
            json={
                "topartists": {
                    "artist": [
                        {
                            "name": "Yo La Tengo",
                            "playcount": "500",
                            "mbid": "3121f5a6-0854-4a15-a3f3-4bd359073857",
                            "@attr": {"rank": "1"},
                        },
                        {
                            "name": "Sonic Youth",
                            "playcount": "300",
                            "mbid": "",
                            "@attr": {"rank": "2"},
                        },
                    ],
                    "@attr": {
                        "page": "1",
                        "perPage": "200",
                        "total": "2",
                        "totalPages": "1",
                    },
                }
            },
            request=httpx.Request("GET", "https://example.com"),
        )
        with patch.object(client._http, "get", return_value=mock_response):
            artists = client.get_top_artists("testuser")
            assert len(artists) == 2
            assert artists[0]["name"] == "Yo La Tengo"
            assert artists[0]["playcount"] == "500"
            assert artists[1]["name"] == "Sonic Youth"

    def test_multiple_pages(self, client):
        page1 = httpx.Response(
            200,
            json={
                "topartists": {
                    "artist": [
                        {
                            "name": "Artist1",
                            "playcount": "100",
                            "mbid": "",
                            "@attr": {"rank": "1"},
                        }
                    ],
                    "@attr": {
                        "page": "1",
                        "perPage": "1",
                        "total": "2",
                        "totalPages": "2",
                    },
                }
            },
            request=httpx.Request("GET", "https://example.com"),
        )
        page2 = httpx.Response(
            200,
            json={
                "topartists": {
                    "artist": [
                        {
                            "name": "Artist2",
                            "playcount": "50",
                            "mbid": "",
                            "@attr": {"rank": "2"},
                        }
                    ],
                    "@attr": {
                        "page": "2",
                        "perPage": "1",
                        "total": "2",
                        "totalPages": "2",
                    },
                }
            },
            request=httpx.Request("GET", "https://example.com"),
        )
        with (
            patch.object(client._http, "get", side_effect=[page1, page2]),
            patch("time.sleep"),
        ):
            artists = client.get_top_artists("testuser", limit=1)
            assert len(artists) == 2

    def test_api_error_raises(self, client):
        mock_response = httpx.Response(
            200,
            json={"error": 6, "message": "User not found"},
            request=httpx.Request("GET", "https://example.com"),
        )
        with (
            patch.object(client._http, "get", return_value=mock_response),
            pytest.raises(LastfmApiError, match="User not found"),
        ):
            client.get_top_artists("nonexistent")

    def test_rate_limit_retries(self, client):
        rate_limited = httpx.Response(
            200,
            json={"error": 29, "message": "Rate limit exceeded"},
            request=httpx.Request("GET", "https://example.com"),
        )
        success = httpx.Response(
            200,
            json={
                "topartists": {
                    "artist": [
                        {
                            "name": "Artist1",
                            "playcount": "100",
                            "mbid": "",
                            "@attr": {"rank": "1"},
                        }
                    ],
                    "@attr": {
                        "page": "1",
                        "perPage": "200",
                        "total": "1",
                        "totalPages": "1",
                    },
                }
            },
            request=httpx.Request("GET", "https://example.com"),
        )
        with (
            patch.object(client._http, "get", side_effect=[rate_limited, success]),
            patch("time.sleep"),
        ):
            artists = client.get_top_artists("testuser")
            assert len(artists) == 1


class TestGetTopAlbums:
    def test_single_page(self, client):
        mock_response = httpx.Response(
            200,
            json={
                "topalbums": {
                    "album": [
                        {
                            "name": "I Can Hear the Heart Beating as One",
                            "playcount": "200",
                            "mbid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                            "artist": {
                                "name": "Yo La Tengo",
                                "mbid": "3121f5a6-0854-4a15-a3f3-4bd359073857",
                            },
                            "@attr": {"rank": "1"},
                        }
                    ],
                    "@attr": {
                        "page": "1",
                        "perPage": "200",
                        "total": "1",
                        "totalPages": "1",
                    },
                }
            },
            request=httpx.Request("GET", "https://example.com"),
        )
        with patch.object(client._http, "get", return_value=mock_response):
            albums = client.get_top_albums("testuser")
            assert len(albums) == 1
            assert albums[0]["name"] == "I Can Hear the Heart Beating as One"
            assert albums[0]["artist"]["name"] == "Yo La Tengo"
