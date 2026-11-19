"""GET a URL the module was given, on the public internet only.

A URL a tool takes from the model (a page to read) names a host the module
does not control, while the module runs next to the engine's own services.
:func:`fetch_public` keeps such a request on the public internet, with the
rules of core's ``naas_abi_core.utils.outbound`` (the modules cannot import
core):

- only ``http`` and ``https``, on the first request and on every redirect;
- local and internal names (``localhost``, ``*.local``, ``*.internal``, names
  without a dot, the cloud metadata names) are refused before any lookup;
- each host name is resolved once, when its connection opens, and every
  address it resolves to must be public: loopback, private, link-local,
  shared (CGNAT), unspecified, multicast and reserved addresses are refused.
  An IPv6 address that carries an IPv4 one (mapped, 6to4, NAT64) is judged by
  the IPv4 address it carries;
- the connection goes to the address that was checked, never to a second
  lookup of the name; the ``Host`` header and TLS server name stay the URL's
  own, so certificates are verified against the name;
- redirects are followed one hop at a time, each hop checked the same way;
- proxy settings from the environment are ignored;
- the body is capped (``max_bytes``) and the whole exchange bounded by one
  deadline (``timeout``).
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import anyio
import anyio.to_thread
import httpcore
import httpx

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_REDIRECTS = 5

_SCHEMES = frozenset({"http", "https"})
_LOCAL_NAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
        "metadata",
        "metadata.google.internal",
        "metadata.goog",
        "instance-data",
    }
)
_LOCAL_SUFFIXES = (".localhost", ".local", ".internal", ".home.arpa", ".lan")
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_SHARED = ipaddress.ip_network("100.64.0.0/10")
_REDIRECTS = frozenset({301, 302, 303, 307, 308})


class FetchError(Exception):
    """The page could not be fetched (network failure, timeout, redirects)."""


class FetchRefused(FetchError):
    """The URL, or an address its host resolves to, is not a public one."""


def _normalize(host: str) -> str:
    return (host or "").strip().strip("[]").rstrip(".").lower()


def _embedded_ipv4(ip: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip.sixtofour is not None:
        return ip.sixtofour
    if ip in _NAT64:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return None


def _public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return not (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_unspecified
        or ip.is_multicast
        or ip.is_reserved
        or not ip.is_global
        or (isinstance(ip, ipaddress.IPv4Address) and ip in _SHARED)
    )


def is_public_address(address: str) -> bool:
    """Whether ``address`` is a public address (see the module doc)."""
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    candidates: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = [ip]
    if isinstance(ip, ipaddress.IPv6Address):
        embedded = _embedded_ipv4(ip)
        if embedded is not None:
            candidates = [embedded]
        elif ip.teredo is not None:
            candidates = list(ip.teredo)
    return all(_public(candidate) for candidate in candidates)


def _check_host(name: str) -> None:
    if not name:
        raise FetchRefused("the URL has no host")
    try:
        ipaddress.ip_address(name.split("%", 1)[0])
    except ValueError:
        pass
    else:
        if not is_public_address(name):
            raise FetchRefused("it does not resolve to a public address")
        return
    if name in _LOCAL_NAMES or name.endswith(_LOCAL_SUFFIXES) or "." not in name:
        raise FetchRefused("it is a local network name")


def check_url(url: str) -> None:
    """Refuse a URL whose scheme or host is not allowed, without any lookup."""
    try:
        parts = urlsplit((url or "").strip())
        scheme = parts.scheme.lower()
        host = _normalize(parts.hostname or "")
        parts.port  # noqa: B018 - raises on a port that is not a number
    except ValueError as exc:
        raise FetchRefused("the URL is not valid") from exc
    if scheme not in _SCHEMES:
        raise FetchRefused("only http and https URLs are allowed")
    _check_host(host)


def resolve_public(host: str, port: int) -> list[str]:
    """Resolve ``host`` once; every address it resolves to must be public."""
    name = _normalize(host)
    _check_host(name)
    try:
        infos = socket.getaddrinfo(name, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise FetchRefused("the host name does not resolve") from exc
    addresses: list[str] = []
    for info in infos:
        address = str(info[4][0])
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise FetchRefused("the host name does not resolve")
    if not all(is_public_address(address) for address in addresses):
        raise FetchRefused("it does not resolve to a public address")
    return addresses


class _PublicBackend(httpcore.AsyncNetworkBackend):
    """Opens TCP connections only to checked addresses of the requested host;
    the lookup runs in a thread."""

    def __init__(self) -> None:
        self._inner = httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        addresses = await anyio.to_thread.run_sync(
            lambda: resolve_public(host, port), abandon_on_cancel=True
        )
        last: Exception | None = None
        for address in addresses:
            try:
                return await self._inner.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last = exc
        assert last is not None
        raise last

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        raise FetchRefused("unix sockets are not allowed")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


class PublicTransport(httpx.AsyncHTTPTransport):
    """Async httpx transport whose connections reach public addresses only."""

    def __init__(self) -> None:
        super().__init__(trust_env=False)
        self._pool = httpcore.AsyncConnectionPool(  # type: ignore[assignment]
            ssl_context=httpx.create_ssl_context(),
            network_backend=_PublicBackend(),
            http1=True,
            http2=False,
        )


@dataclass(frozen=True)
class PublicPage:
    """A response read through :func:`fetch_public`, body capped."""

    url: str
    status_code: int
    headers: Mapping[str, str]
    content: bytes
    truncated: bool

    @property
    def text(self) -> str:
        """Body decoded with its declared charset, or UTF-8."""
        charset = None
        for part in (self.headers.get("content-type") or "").split(";")[1:]:
            key, _, value = part.partition("=")
            if key.strip().lower() == "charset" and value.strip():
                charset = value.strip().strip("\"'")
        try:
            return self.content.decode(charset or "utf-8", errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")


async def fetch_public(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    transport: httpx.AsyncBaseTransport | None = None,
) -> PublicPage:
    """GET ``url`` on the public internet, following checked redirects.

    Reads at most ``max_bytes`` of the body; ``timeout`` bounds the whole
    exchange. Any status is returned: the caller decides what a 404 means.
    ``transport`` replaces the public-address transport (tests only).

    Raises :class:`FetchRefused` when the URL or a destination is not allowed,
    and :class:`FetchError` for every other failure.
    """
    current = (url or "").strip()
    try:
        with anyio.fail_after(timeout):
            async with httpx.AsyncClient(
                transport=transport or PublicTransport(),
                trust_env=False,
                timeout=timeout,
                follow_redirects=False,
            ) as client:
                for _ in range(max_redirects + 1):
                    check_url(current)
                    async with client.stream(
                        "GET", current, headers=dict(headers or {})
                    ) as response:
                        location = response.headers.get("location")
                        if response.status_code in _REDIRECTS and location:
                            current = str(response.url.join(location))
                            continue
                        chunks: list[bytes] = []
                        size = 0
                        truncated = False
                        async for chunk in response.aiter_bytes():
                            room = max_bytes - size
                            if len(chunk) > room:
                                chunks.append(chunk[:room])
                                truncated = True
                                break
                            chunks.append(chunk)
                            size += len(chunk)
                        return PublicPage(
                            url=str(response.url),
                            status_code=response.status_code,
                            headers=dict(response.headers),
                            content=b"".join(chunks),
                            truncated=truncated,
                        )
                raise FetchError("too many redirects")
    except FetchError:
        raise
    except (TimeoutError, httpx.TimeoutException):
        raise FetchError("the request timed out") from None
    except (httpx.HTTPError, httpx.InvalidURL, OSError):
        raise FetchError("the host could not be reached") from None
