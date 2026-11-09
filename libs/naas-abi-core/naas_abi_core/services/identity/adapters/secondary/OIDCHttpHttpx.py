"""``OIDCHttpPort`` over httpx: discovery, JWKS and token endpoints.

Responses are read up to ``max_bytes``; redirects are not followed (an
issuer's documents are served at their own URLs). ``Cache-Control: max-age``
sets how long a document may be cached; ``no-store`` and ``no-cache`` mean not
at all.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

import httpx

from naas_abi_core.services.identity.IdentityPorts import (
    HttpJSON,
    OIDCHttpPort,
    ProviderUnavailableError,
)

_MAX_AGE = re.compile(r"(?:^|,)\s*max-age\s*=\s*(\d+)", re.IGNORECASE)
_NO_CACHE = re.compile(r"(?:^|,)\s*(no-store|no-cache)\b", re.IGNORECASE)


def cache_max_age(cache_control: str | None) -> float | None:
    if not cache_control:
        return None
    if _NO_CACHE.search(cache_control):
        return 0.0
    match = _MAX_AGE.search(cache_control)
    return float(match.group(1)) if match else None


class OIDCHttpHttpx(OIDCHttpPort):
    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        max_bytes: int = 1024 * 1024,
        verify: bool | str = True,
        client: httpx.Client | None = None,
    ) -> None:
        self._max_bytes = max_bytes
        self._client = client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=False,
            verify=verify,
            headers={"Accept": "application/json", "User-Agent": "naas-abi-identity"},
        )

    def get_json(self, url: str) -> HttpJSON:
        try:
            response = self._client.get(url)
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"GET {url}: {exc}") from exc
        if response.status_code != 200:
            raise ProviderUnavailableError(f"GET {url}: HTTP {response.status_code}")
        body = self._json(response, url)
        return HttpJSON(body, cache_max_age(response.headers.get("cache-control")))

    def post_form(
        self,
        url: str,
        data: Mapping[str, str],
        *,
        basic_auth: tuple[str, str] | None = None,
    ) -> tuple[int, Mapping[str, Any]]:
        try:
            response = self._client.post(
                url,
                data=dict(data),
                auth=httpx.BasicAuth(*basic_auth)
                if basic_auth
                else httpx.USE_CLIENT_DEFAULT,
            )
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"POST {url}: {exc}") from exc
        if response.status_code >= 500:
            raise ProviderUnavailableError(f"POST {url}: HTTP {response.status_code}")
        if not response.content:
            return response.status_code, {}
        try:
            return response.status_code, self._json(response, url)
        except ProviderUnavailableError:
            if response.status_code == 200:
                raise
            return response.status_code, {}

    def _json(self, response: httpx.Response, url: str) -> Mapping[str, Any]:
        if len(response.content) > self._max_bytes:
            raise ProviderUnavailableError(f"{url}: the answer is too large")
        try:
            body = json.loads(response.content)
        except ValueError as exc:
            raise ProviderUnavailableError(f"{url}: not JSON") from exc
        if not isinstance(body, dict):
            raise ProviderUnavailableError(f"{url}: not a JSON object")
        return body

    def close(self) -> None:
        self._client.close()
