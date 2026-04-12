import hashlib
import time
from urllib.parse import urlencode

import httpx

BASE_URL = "https://ws.audioscrobbler.com/2.0/"
AUTH_URL = "https://www.last.fm/api/auth/"


class LastfmAuthError(Exception):
    pass


class LastfmApiError(Exception):
    pass


class LastfmClient:
    def __init__(self, api_key: str, shared_secret: str, callback_url: str) -> None:
        self._api_key = api_key
        self._shared_secret = shared_secret
        self._callback_url = callback_url
        self._http = httpx.Client(timeout=30)

    def get_auth_url(self) -> str:
        params = {"api_key": self._api_key, "cb": self._callback_url}
        return f"{AUTH_URL}?{urlencode(params)}"

    def _build_signature(self, params: dict[str, str]) -> str:
        filtered = {k: v for k, v in params.items() if k != "format"}
        sorted_params = sorted(filtered.items())
        sig_input = "".join(f"{k}{v}" for k, v in sorted_params) + self._shared_secret
        return hashlib.md5(sig_input.encode()).hexdigest()

    def exchange_token(self, token: str) -> tuple[str, str]:
        params = {
            "method": "auth.getSession",
            "api_key": self._api_key,
            "token": token,
        }
        params["api_sig"] = self._build_signature(params)
        params["format"] = "json"

        response = self._http.get(BASE_URL, params=params)
        data = response.json()

        if "error" in data:
            raise LastfmAuthError(data["message"])

        session = data["session"]
        return session["key"], session["name"]

    def _request(self, params: dict[str, str], retry: bool = True) -> dict:
        params["api_key"] = self._api_key
        params["format"] = "json"

        response = self._http.get(BASE_URL, params=params)
        data = response.json()

        if "error" in data:
            if data["error"] == 29 and retry:
                time.sleep(1)
                return self._request(params, retry=False)
            raise LastfmApiError(data["message"])

        return data

    def get_top_artists(
        self, user: str, period: str = "overall", limit: int = 200
    ) -> list[dict]:
        all_artists = []
        page = 1

        while True:
            data = self._request(
                {
                    "method": "user.getTopArtists",
                    "user": user,
                    "period": period,
                    "limit": str(limit),
                    "page": str(page),
                }
            )
            artists = data["topartists"]["artist"]
            all_artists.extend(artists)

            attr = data["topartists"]["@attr"]
            if int(attr["page"]) >= int(attr["totalPages"]):
                break

            page += 1
            time.sleep(0.25)

        return all_artists

    def get_top_albums(
        self, user: str, period: str = "overall", limit: int = 200
    ) -> list[dict]:
        all_albums = []
        page = 1

        while True:
            data = self._request(
                {
                    "method": "user.getTopAlbums",
                    "user": user,
                    "period": period,
                    "limit": str(limit),
                    "page": str(page),
                }
            )
            albums = data["topalbums"]["album"]
            all_albums.extend(albums)

            attr = data["topalbums"]["@attr"]
            if int(attr["page"]) >= int(attr["totalPages"]):
                break

            page += 1
            time.sleep(0.25)

        return all_albums
