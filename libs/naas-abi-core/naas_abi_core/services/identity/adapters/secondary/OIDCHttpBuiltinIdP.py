"""``OIDCHttpPort`` for the built-in IdP: its issuer is reached over NATS.

The built-in IdP is an SDK module with no port of its own: Nexus serves it at
the issuer URL and the engine reads its discovery document, its JWKS and its
token endpoint through the module's ``idp`` app (``abi.app.v1``), never over
HTTP. Every other URL goes to the ``fallback`` port (httpx).

A URL is the IdP's when it is on the issuer's origin and below the issuer's
path. The discovery document of a built-in provider may only name endpoints
there (``provider_keys.parse_metadata``), so a document cannot send the
engine, or the client secret, anywhere else.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode, urlsplit

from naas_abi_core.services.identity.adapters.secondary.OIDCHttpHttpx import (
    cache_max_age,
)
from naas_abi_core.services.identity.IdentityPorts import (
    HttpJSON,
    OIDCHttpPort,
    ProviderUnavailableError,
)

MAX_BYTES = 1024 * 1024


@dataclass(frozen=True)
class AppAnswer:
    status: int
    headers: tuple[tuple[str, str], ...] = ()
    body: bytes = b""

    def header(self, name: str) -> str | None:
        wanted = name.lower()
        return next((v for k, v in self.headers if k.lower() == wanted), None)


class IdPApp(Protocol):
    """The built-in IdP's ``idp`` app: one request, one answer."""

    def request(
        self,
        method: str,
        path: str,
        *,
        query: str = "",
        body: bytes = b"",
        headers: Mapping[str, str] | None = None,
        root_path: str = "",
    ) -> AppAnswer:
        """``ProviderUnavailableError`` when no instance of the module answers."""
        ...


def below_issuer(url: str, issuer: str) -> str | None:
    """The path of ``url`` below ``issuer`` ("/" for the issuer itself), or None
    when ``url`` is elsewhere (another origin, or a path that only looks like it
    is below: a dot segment, an escape)."""
    target, root = urlsplit(url), urlsplit(issuer)
    if (target.scheme, target.netloc) != (root.scheme, root.netloc):
        return None
    base = root.path.rstrip("/")
    if target.path != base and not target.path.startswith(base + "/"):
        return None
    below = target.path[len(base) :] or "/"
    if "%" in below or "\\" in below or "//" in below:
        return None
    if any(part in (".", "..") for part in below.split("/")):
        return None
    return below


class OIDCHttpBuiltinIdP(OIDCHttpPort):
    def __init__(self, fallback: OIDCHttpPort, issuers: Iterable[str]) -> None:
        self._fallback = fallback
        self._issuers = tuple(issuers)
        self._app: IdPApp | None = None

    def attach(self, app: IdPApp | None) -> None:
        """Where the IdP's requests go. The serving engine attaches it once its
        NATS runtime is up; until then a request to the IdP fails as a provider
        that is down does, and is read again on first use."""
        self._app = app

    def get_json(self, url: str) -> HttpJSON:
        route = self._route(url)
        if route is None:
            return self._fallback.get_json(url)
        issuer, path = route
        answer = self._ask("GET", issuer, path, urlsplit(url).query, b"", {})
        if answer.status != 200:
            raise ProviderUnavailableError(f"GET {url}: HTTP {answer.status}")
        return HttpJSON(
            _json(answer.body, url), cache_max_age(answer.header("cache-control"))
        )

    def post_form(
        self,
        url: str,
        data: Mapping[str, str],
        *,
        basic_auth: tuple[str, str] | None = None,
    ) -> tuple[int, Mapping[str, Any]]:
        route = self._route(url)
        if route is None:
            return self._fallback.post_form(url, data, basic_auth=basic_auth)
        issuer, path = route
        headers = {"content-type": "application/x-www-form-urlencoded"}
        if basic_auth is not None:
            import base64

            raw = f"{basic_auth[0]}:{basic_auth[1]}".encode()
            headers["authorization"] = "Basic " + base64.b64encode(raw).decode()
        answer = self._ask(
            "POST",
            issuer,
            path,
            urlsplit(url).query,
            urlencode(dict(data)).encode(),
            headers,
        )
        if answer.status >= 500:
            raise ProviderUnavailableError(f"POST {url}: HTTP {answer.status}")
        if not answer.body:
            return answer.status, {}
        try:
            return answer.status, _json(answer.body, url)
        except ProviderUnavailableError:
            if answer.status == 200:
                raise
            return answer.status, {}

    # -- plumbing ---------------------------------------------------------------------

    def _route(self, url: str) -> tuple[str, str] | None:
        for issuer in self._issuers:
            path = below_issuer(url, issuer)
            if path is not None:
                return issuer, path
        return None

    def _ask(
        self,
        method: str,
        issuer: str,
        path: str,
        query: str,
        body: bytes,
        headers: Mapping[str, str],
    ) -> AppAnswer:
        if self._app is None:
            raise ProviderUnavailableError(
                "The built-in identity provider is not reachable yet: it runs as a "
                "module over NATS (nats.discovery must be configured)"
            )
        return self._app.request(
            method,
            path,
            query=query,
            body=body,
            headers=headers,
            root_path=urlsplit(issuer).path.rstrip("/"),
        )


def _json(body: bytes, url: str) -> Mapping[str, Any]:
    if len(body) > MAX_BYTES:
        raise ProviderUnavailableError(f"{url}: the answer is too large")
    try:
        parsed = json.loads(body)
    except ValueError as exc:
        raise ProviderUnavailableError(f"{url}: not JSON") from exc
    if not isinstance(parsed, dict):
        raise ProviderUnavailableError(f"{url}: not a JSON object")
    return parsed
