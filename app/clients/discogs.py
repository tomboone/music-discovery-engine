# pyright: reportGeneralTypeIssues=false, reportAttributeAccessIssue=false
# (authlib's httpx-based OAuth1Client lacks stubs; pyright can't see that it
# inherits from httpx.Client and that its context-manager / HTTP methods work.)
import time
from urllib.parse import parse_qs

import httpx
from authlib.integrations.httpx_client import OAuth1Client

API_BASE = "https://api.discogs.com"
AUTHORIZE_URL = "https://www.discogs.com/oauth/authorize"


class DiscogsAuthError(Exception):
    pass


class DiscogsApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"{status}: {message}")
        self.status = status
        self.message = message


class DiscogsClient:
    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        callback_url: str,
        user_agent: str,
    ) -> None:
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._callback_url = callback_url
        self._user_agent = user_agent

    def _oauth_client(
        self,
        token: str | None = None,
        token_secret: str | None = None,
    ) -> OAuth1Client:
        return OAuth1Client(
            client_id=self._consumer_key,
            client_secret=self._consumer_secret,
            token=token,
            token_secret=token_secret,
            headers={"User-Agent": self._user_agent},
            timeout=30,
        )

    def get_request_token(self) -> tuple[str, str]:
        with self._oauth_client() as client:
            client.redirect_uri = self._callback_url
            response = client.post(f"{API_BASE}/oauth/request_token")
            if response.status_code != 200:
                raise DiscogsAuthError(
                    f"request_token failed: {response.status_code} {response.text}"
                )
            parsed = parse_qs(response.text)
            return (parsed["oauth_token"][0], parsed["oauth_token_secret"][0])

    def get_authorize_url(self, request_token: str) -> str:
        return f"{AUTHORIZE_URL}?oauth_token={request_token}"

    def exchange_access_token(
        self, request_token: str, request_token_secret: str, verifier: str
    ) -> tuple[str, str]:
        with self._oauth_client(
            token=request_token, token_secret=request_token_secret
        ) as client:
            try:
                token = client.fetch_access_token(
                    f"{API_BASE}/oauth/access_token", verifier=verifier
                )
            except Exception as e:
                raise DiscogsAuthError(f"access_token failed: {e}") from e
            return (token["oauth_token"], token["oauth_token_secret"])

    def get_identity(self, access_token: str, access_token_secret: str) -> str:
        with self._oauth_client(
            token=access_token, token_secret=access_token_secret
        ) as client:
            response = client.get(f"{API_BASE}/oauth/identity")
            if response.status_code != 200:
                raise DiscogsAuthError(
                    f"identity failed: {response.status_code} {response.text}"
                )
            return response.json()["username"]

    def get_collection(
        self, username: str, access_token: str, access_token_secret: str
    ) -> list[dict]:
        return self._paginated_get(
            f"{API_BASE}/users/{username}/collection/folders/0/releases",
            access_token,
            access_token_secret,
            items_key="releases",
            extra_params={"sort": "added", "sort_order": "desc"},
        )

    def get_wantlist(
        self, username: str, access_token: str, access_token_secret: str
    ) -> list[dict]:
        return self._paginated_get(
            f"{API_BASE}/users/{username}/wants",
            access_token,
            access_token_secret,
            items_key="wants",
        )

    def _paginated_get(
        self,
        url: str,
        access_token: str,
        access_token_secret: str,
        items_key: str,
        extra_params: dict | None = None,
    ) -> list[dict]:
        results: list[dict] = []
        page = 1

        with self._oauth_client(
            token=access_token, token_secret=access_token_secret
        ) as client:
            while True:
                params = {"page": str(page), "per_page": "100"}
                if extra_params:
                    params.update(extra_params)
                response = self._request_with_retries(client, url, params)

                self._respect_rate_limit(response)

                body = response.json()
                results.extend(body.get(items_key, []))
                pagination = body.get("pagination", {})
                if page >= pagination.get("pages", 1):
                    break
                page += 1

        return results

    @staticmethod
    def _request_with_retries(
        client: OAuth1Client, url: str, params: dict, attempts: int = 2
    ) -> httpx.Response:
        for _attempt in range(attempts):
            response = client.get(url, params=params)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 5))
                time.sleep(retry_after)
                continue
            if response.status_code >= 400:
                raise DiscogsApiError(response.status_code, response.text)
            return response
        raise DiscogsApiError(429, "rate limit exceeded after retries")

    @staticmethod
    def _respect_rate_limit(response: httpx.Response) -> None:
        remaining_header = response.headers.get("X-Discogs-Ratelimit-Remaining")
        if remaining_header is not None:
            try:
                remaining = int(remaining_header)
            except ValueError:
                return
            if remaining < 2:
                time.sleep(1)
