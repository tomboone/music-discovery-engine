import pytest
import respx
from httpx import Response

from app.clients.discogs import DiscogsAuthError, DiscogsClient


def _make_client():
    return DiscogsClient(
        consumer_key="ck",
        consumer_secret="cs",
        callback_url="https://example.com/cb",
        user_agent="TestAgent/0.1",
    )


@respx.mock
def test_get_request_token_parses_response():
    respx.post("https://api.discogs.com/oauth/request_token").mock(
        return_value=Response(
            200,
            text="oauth_token=rt_abc&oauth_token_secret=rts_xyz&oauth_callback_confirmed=true",
        )
    )
    client = _make_client()
    token, secret = client.get_request_token()
    assert token == "rt_abc"
    assert secret == "rts_xyz"


@respx.mock
def test_get_request_token_raises_on_error():
    respx.post("https://api.discogs.com/oauth/request_token").mock(
        return_value=Response(401, text="Invalid consumer credentials")
    )
    client = _make_client()
    with pytest.raises(DiscogsAuthError):
        client.get_request_token()


@respx.mock
def test_exchange_access_token_parses_response():
    respx.post("https://api.discogs.com/oauth/access_token").mock(
        return_value=Response(200, text="oauth_token=at_abc&oauth_token_secret=ats_xyz")
    )
    client = _make_client()
    token, secret = client.exchange_access_token("rt", "rts", "verifier_v")
    assert token == "at_abc"
    assert secret == "ats_xyz"


@respx.mock
def test_exchange_access_token_verifier_not_in_body():
    """oauth_verifier must NOT appear in the request body (Bug 2 regression).

    The verifier belongs in the Authorization header (per RFC 5849 §3.5.1).
    The old manual-signing implementation put it in BOTH header and body simultaneously,
    which is a double-submission bug. authlib's fetch_access_token only sends it in the
    header, so the body should be empty.
    """
    captured_body: list[bytes] = []

    def capture(request, *args, **kwargs):
        captured_body.append(request.content)
        return Response(200, text="oauth_token=at_abc&oauth_token_secret=ats_xyz")

    respx.post("https://api.discogs.com/oauth/access_token").mock(side_effect=capture)
    client = _make_client()
    client.exchange_access_token("rt", "rts", "verifier_v")
    assert captured_body, "request was never made"
    assert b"oauth_verifier" not in captured_body[0], (
        "oauth_verifier must not appear in the request body (header-only transport)"
    )


@respx.mock
def test_exchange_access_token_raises_on_error():
    respx.post("https://api.discogs.com/oauth/access_token").mock(
        return_value=Response(401, text="Bad verifier")
    )
    client = _make_client()
    with pytest.raises(DiscogsAuthError):
        client.exchange_access_token("rt", "rts", "bad")


@respx.mock
def test_get_identity_returns_username():
    respx.get("https://api.discogs.com/oauth/identity").mock(
        return_value=Response(200, json={"id": 123, "username": "audiophilesasquatch"})
    )
    client = _make_client()
    username = client.get_identity("at", "ats")
    assert username == "audiophilesasquatch"


def test_get_authorize_url():
    client = _make_client()
    url = client.get_authorize_url("rt_abc")
    assert url == "https://www.discogs.com/oauth/authorize?oauth_token=rt_abc"


@respx.mock
def test_get_collection_paginated():
    base = "https://api.discogs.com/users/tom/collection/folders/0/releases"
    respx.get(
        base,
        params={"page": "1", "per_page": "100", "sort": "added", "sort_order": "desc"},
    ).mock(
        return_value=Response(
            200,
            json={
                "pagination": {"page": 1, "pages": 2, "per_page": 100, "items": 150},
                "releases": [
                    {
                        "id": 1,
                        "basic_information": {
                            "title": "X",
                            "master_id": 10,
                            "artists": [{"id": 5, "name": "A"}],
                        },
                    },
                    {
                        "id": 2,
                        "basic_information": {
                            "title": "Y",
                            "master_id": 11,
                            "artists": [{"id": 6, "name": "B"}],
                        },
                    },
                ],
            },
        )
    )
    respx.get(
        base,
        params={"page": "2", "per_page": "100", "sort": "added", "sort_order": "desc"},
    ).mock(
        return_value=Response(
            200,
            json={
                "pagination": {"page": 2, "pages": 2, "per_page": 100, "items": 150},
                "releases": [
                    {
                        "id": 3,
                        "basic_information": {
                            "title": "Z",
                            "master_id": 12,
                            "artists": [{"id": 7, "name": "C"}],
                        },
                    },
                ],
            },
        )
    )
    client = _make_client()
    items = client.get_collection("tom", "at", "ats")
    assert len(items) == 3
    assert items[0]["basic_information"]["title"] == "X"
    assert items[2]["basic_information"]["title"] == "Z"


@respx.mock
def test_get_wantlist_paginated():
    base = "https://api.discogs.com/users/tom/wants"
    respx.get(base, params={"page": "1", "per_page": "100"}).mock(
        return_value=Response(
            200,
            json={
                "pagination": {"page": 1, "pages": 1, "per_page": 100, "items": 1},
                "wants": [
                    {
                        "id": 99,
                        "basic_information": {
                            "title": "W",
                            "master_id": 200,
                            "artists": [{"id": 1, "name": "WA"}],
                        },
                    }
                ],
            },
        )
    )
    client = _make_client()
    items = client.get_wantlist("tom", "at", "ats")
    assert len(items) == 1
    assert items[0]["basic_information"]["title"] == "W"


@respx.mock
def test_get_collection_429_retries_then_succeeds(monkeypatch):
    import time as time_mod

    sleeps = []
    monkeypatch.setattr(time_mod, "sleep", lambda s: sleeps.append(s))

    base = "https://api.discogs.com/users/tom/collection/folders/0/releases"
    call_count = {"n": 0}

    def _handler(request):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return Response(429, headers={"Retry-After": "2"}, text="rate limited")
        return Response(
            200,
            json={
                "pagination": {"page": 1, "pages": 1, "per_page": 100, "items": 1},
                "releases": [
                    {
                        "id": 1,
                        "basic_information": {
                            "title": "T",
                            "master_id": 1,
                            "artists": [{"id": 1, "name": "A"}],
                        },
                    },
                ],
            },
        )

    respx.get(base).mock(side_effect=_handler)
    client = _make_client()
    items = client.get_collection("tom", "at", "ats")
    assert len(items) == 1
    assert 2 in sleeps  # Retry-After honored


@respx.mock
def test_get_collection_429_twice_raises(monkeypatch):
    import time as time_mod

    monkeypatch.setattr(time_mod, "sleep", lambda s: None)

    base = "https://api.discogs.com/users/tom/collection/folders/0/releases"
    respx.get(base).mock(return_value=Response(429, headers={"Retry-After": "1"}))
    client = _make_client()
    from app.clients.discogs import DiscogsApiError

    with pytest.raises(DiscogsApiError) as exc_info:
        client.get_collection("tom", "at", "ats")
    assert exc_info.value.status == 429
