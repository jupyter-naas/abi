"""A provider's admin API over httpx: JSON in, JSON out, bearer authorization.

Redirects are not followed and answers are read up to ``max_bytes``. A transport
failure and a 5xx answer are ``ProviderUnavailableError``; every other status
is the caller's to read, with the parsed JSON body (``None`` when there is none).
The base URL is fixed at construction, so a path argument can never name
another host.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from naas_abi_core.services.identity.IdentityPorts import (
    ProviderUnavailableError,
    ProvisioningError,
)


class AdminHttp:
    def __init__(
        self,
        base_url: str,
        *,
        headers: Callable[[], Mapping[str, str]] | None = None,
        timeout_seconds: float = 10.0,
        max_bytes: int = 1024 * 1024,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._headers = headers or (dict)
        self._max_bytes = max_bytes
        self._httpx = client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=False,
            headers={"Accept": "application/json", "User-Agent": "naas-abi-identity"},
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> tuple[int, Any, Mapping[str, str]]:
        """``(status, JSON body or None, response headers)``."""
        if not path.startswith("/"):
            raise ValueError("An admin API path starts with /")
        url = self.base_url + path
        try:
            response = self._httpx.request(
                method,
                url,
                json=json_body,
                params=dict(params) if params else None,
                data=dict(data) if data else None,
                headers={**self._headers(), **(headers or {})},
            )
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"{method} {url}: {exc}") from exc
        if response.status_code >= 500:
            raise ProviderUnavailableError(
                f"{method} {url}: HTTP {response.status_code}"
            )
        if len(response.content) > self._max_bytes:
            raise ProviderUnavailableError(f"{method} {url}: the answer is too large")
        body: Any = None
        if response.content:
            try:
                body = json.loads(response.content)
            except ValueError:
                body = None
        return response.status_code, body, dict(response.headers)


class ClientCredentialsToken:
    """A bearer token from an OAuth client credentials grant, kept until it is
    about to expire (``skew_seconds`` before)."""

    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        *,
        timeout_seconds: float = 10.0,
        skew_seconds: float = 30.0,
        clock: Callable[[], float] = time.time,
        client: httpx.Client | None = None,
    ) -> None:
        self._url = token_url
        self._credentials = (client_id, client_secret)
        self._skew = skew_seconds
        self._clock = clock
        self._httpx = client or httpx.Client(
            timeout=timeout_seconds, follow_redirects=False
        )
        self._lock = threading.Lock()
        self._token: tuple[str, float] | None = None

    def headers(self) -> Mapping[str, str]:
        with self._lock:
            now = self._clock()
            if self._token is None or self._token[1] - self._skew <= now:
                self._token = self._fetch(now)
            return {"Authorization": f"Bearer {self._token[0]}"}

    def _fetch(self, now: float) -> tuple[str, float]:
        try:
            response = self._httpx.post(
                self._url,
                data={"grant_type": "client_credentials"},
                auth=httpx.BasicAuth(*self._credentials),
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"POST {self._url}: {exc}") from exc
        if response.status_code >= 500:
            raise ProviderUnavailableError(
                f"POST {self._url}: HTTP {response.status_code}"
            )
        try:
            body = response.json()
            token = str(body["access_token"])
            lifetime = float(body.get("expires_in", 60))
        except (ValueError, KeyError, TypeError) as exc:
            raise ProvisioningError(
                f"The provider refused the admin client's credentials "
                f"(HTTP {response.status_code})"
            ) from exc
        return token, now + lifetime
