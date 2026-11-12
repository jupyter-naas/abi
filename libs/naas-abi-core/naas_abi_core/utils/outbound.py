"""One HTTP client for requests sent to URLs the platform was given.

A URL that comes from a user, a model, a fetched page or a stored setting names
a host the platform does not control. Every request to such a URL goes through
the clients here, which keep it on the public internet:

- only ``http`` and ``https`` are spoken, on the first request and on every
  redirect (httpx has no handler for any other scheme);
- each host name is resolved once, when its connection opens, and every
  address it resolves to must be public: loopback, private, link-local,
  shared (CGNAT), unspecified, multicast and reserved addresses are refused.
  An IPv6 address that carries an IPv4 one (mapped, 6to4, NAT64) is judged by
  the IPv4 address it carries;
- the connection goes to the address that was checked, never to a second
  lookup of the name, while the ``Host`` header and TLS server name stay the
  URL's own, so certificates are verified against the name;
- local and internal names (``localhost``, ``*.local``, ``*.internal``, names
  without a dot, the cloud metadata names) are refused before any lookup;
- redirects open new connections, so every hop is checked the same way;
- proxy settings from the environment are ignored: a proxy would make the
  connection on the client's behalf, past the address check;
- :func:`fetch` and :func:`afetch` cap the size of the body, and bound the
  whole exchange (lookups, connections, headers, redirects and body) by one
  deadline.

A deployment may name origins it trusts on its own network (a model server on
the private network, for example) in ``allowed_origins``: ``host:port``, or a
URL (``http://host:port``), or a bare host, which stands for its ports 80 and
443. A listed origin skips the address check and nothing else; another port of
the same host is checked like any other destination.
"""

from __future__ import annotations

import ipaddress
import socket
import threading
import time
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import anyio
import anyio.to_thread
import httpcore
import httpx

DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_REDIRECTS = 5
# A name lookup has no timeout of its own: it is waited for this long at most.
RESOLVE_TIMEOUT_SECONDS = 10.0

_SCHEMES = frozenset({"http", "https"})
_DEFAULT_PORTS = {"http": 80, "https": 443}
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
# Not every Python release lists 100.64.0.0/10 as non-global; name it here.
_SHARED = ipaddress.ip_network("100.64.0.0/10")

# ``OutboundRefused.reason`` values.
INVALID_URL = "invalid-url"
SCHEME = "scheme"
NO_HOST = "no-host"
LOCAL_NAME = "local-name"
NOT_PUBLIC = "not-public"
UNRESOLVED = "unresolved"
UNIX_SOCKET = "unix-socket"


class OutboundError(Exception):
    """The request could not be completed (network failure, timeout, redirects)."""


class OutboundRefused(OutboundError):
    """The URL or the address its host resolves to is not allowed.

    ``reason`` names why (one of the reason constants), for callers that word
    their own message; None when the refusal came from elsewhere.
    """

    def __init__(self, message: str, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason


def _refused(reason: str) -> OutboundRefused:
    messages = {
        INVALID_URL: "the URL is not valid",
        SCHEME: "only http and https URLs are allowed",
        NO_HOST: "the URL has no host",
        LOCAL_NAME: "it is a local network name",
        NOT_PUBLIC: "it does not resolve to a public address",
        UNRESOLVED: "the host name does not resolve",
        UNIX_SOCKET: "unix sockets are not allowed",
    }
    return OutboundRefused(messages[reason], reason)


def normalize_host(host: str) -> str:
    """Lower-case host name without a trailing dot or IPv6 brackets."""
    return (host or "").strip().strip("[]").rstrip(".").lower()


Origin = tuple[str, int]


def parse_origins(entries: Iterable[str] | None) -> frozenset[Origin]:
    """``(host, port)`` pairs from ``host:port``, URL or bare host entries.

    A bare host stands for its ports 80 and 443. Entries that do not parse are
    left out.
    """
    origins: set[Origin] = set()
    for entry in entries or ():
        text = str(entry).strip()
        if not text:
            continue
        try:
            parts = urlsplit(text if "://" in text else f"//{text}")
            host = normalize_host(parts.hostname or "")
            port = parts.port
        except ValueError:
            continue
        if not host:
            continue
        if port is None and parts.scheme in _DEFAULT_PORTS:
            port = _DEFAULT_PORTS[parts.scheme]
        if port is None:
            origins.update({(host, 80), (host, 443)})
        else:
            origins.add((host, port))
    return frozenset(origins)


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


def address_refusal(address: str) -> str | None:
    """Why ``address`` is not a public address, or None when it is.

    An IPv6 address carrying an IPv4 one (mapped, 6to4, NAT64) is judged by
    the IPv4 address; a Teredo address by both of the IPv4 addresses it holds.
    """
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return "the address is not valid"
    candidates: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = [ip]
    if isinstance(ip, ipaddress.IPv6Address):
        embedded = _embedded_ipv4(ip)
        if embedded is not None:
            candidates = [embedded]
        elif ip.teredo is not None:
            candidates = list(ip.teredo)
    if all(_public(candidate) for candidate in candidates):
        return None
    return "it does not resolve to a public address"


def _host_refusal_reason(name: str) -> str | None:
    if not name:
        return NO_HOST
    try:
        ipaddress.ip_address(name.split("%", 1)[0])
    except ValueError:
        pass
    else:
        return NOT_PUBLIC if address_refusal(name) else None
    if name in _LOCAL_NAMES or name.endswith(_LOCAL_SUFFIXES) or "." not in name:
        return LOCAL_NAME
    return None


def host_refusal(host: str) -> str | None:
    """Why ``host`` is refused before any lookup, or None."""
    reason = _host_refusal_reason(normalize_host(host))
    return None if reason is None else str(_refused(reason))


def _getaddrinfo(name: str, port: int, timeout: float) -> list[Any]:
    """``socket.getaddrinfo``, waited for ``timeout`` seconds at most."""
    outcome: dict[str, Any] = {}

    def run() -> None:
        try:
            outcome["infos"] = socket.getaddrinfo(name, port, type=socket.SOCK_STREAM)
        except BaseException as exc:  # noqa: BLE001 - handed to the caller
            outcome["error"] = exc

    worker = threading.Thread(target=run, name="outbound-resolve", daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        raise OutboundError("the host name took too long to resolve")
    if "error" in outcome:
        raise _refused(UNRESOLVED) from outcome["error"]
    return list(outcome["infos"])


def resolve_public(
    host: str,
    port: int,
    *,
    allowed_origins: Iterable[Origin] | None = None,
    timeout: float = RESOLVE_TIMEOUT_SECONDS,
) -> list[str]:
    """Resolve ``host`` once and return its addresses, all checked.

    Raises :class:`OutboundRefused` when the host is a local name, when it does
    not resolve, or when any of its addresses is not public. An origin in
    ``allowed_origins`` (``(host, port)`` pairs, see :func:`parse_origins`) is
    resolved without the address check.
    """
    name = normalize_host(host)
    allowed = (name, port) in frozenset(allowed_origins or ())
    if not allowed:
        reason = _host_refusal_reason(name)
        if reason is not None:
            raise _refused(reason)
    addresses: list[str] = []
    for info in _getaddrinfo(name, port, timeout):
        address = str(info[4][0])
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise _refused(UNRESOLVED)
    if not allowed and any(address_refusal(address) for address in addresses):
        raise _refused(NOT_PUBLIC)
    return addresses


def url_origin(url: str) -> Origin:
    """The ``(host, port)`` of an http(s) URL; :class:`OutboundRefused` otherwise."""
    try:
        parts = urlsplit((url or "").strip())
        scheme = parts.scheme.lower()
        host = normalize_host(parts.hostname or "")
        port = parts.port
    except ValueError as exc:
        raise _refused(INVALID_URL) from exc
    if scheme not in _SCHEMES:
        raise _refused(SCHEME)
    if not host:
        raise _refused(NO_HOST)
    return host, port if port is not None else _DEFAULT_PORTS[scheme]


def check_url(url: str, *, allowed_origins: Iterable[str] | None = None) -> None:
    """Refuse a URL whose scheme or host is not allowed, without any lookup."""
    origin = url_origin(url)
    if origin in parse_origins(allowed_origins):
        return
    reason = _host_refusal_reason(origin[0])
    if reason is not None:
        raise _refused(reason)


_TIMED_OUT = "the request timed out"


class _Deadline:
    """One deadline for a whole exchange, shared by its connections and streams."""

    def __init__(self, seconds: float) -> None:
        self._at = time.monotonic() + seconds

    def bound(self, timeout: float | None) -> float:
        """``timeout`` cut to the time left; :class:`OutboundError` once none is."""
        left = self._at - time.monotonic()
        if left <= 0:
            raise OutboundError(_TIMED_OUT)
        return left if timeout is None else min(timeout, left)


class _DeadlineStream(httpcore.NetworkStream):
    """A network stream whose every operation ends by the exchange's deadline."""

    def __init__(self, inner: httpcore.NetworkStream, deadline: _Deadline) -> None:
        self._inner = inner
        self._deadline = deadline

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        return self._inner.read(max_bytes, timeout=self._deadline.bound(timeout))

    def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self._inner.write(buffer, timeout=self._deadline.bound(timeout))

    def close(self) -> None:
        self._inner.close()

    def start_tls(
        self,
        ssl_context: Any,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ) -> httpcore.NetworkStream:
        upgraded = self._inner.start_tls(
            ssl_context,
            server_hostname=server_hostname,
            timeout=self._deadline.bound(timeout),
        )
        return _DeadlineStream(upgraded, self._deadline)

    def get_extra_info(self, info: str) -> Any:
        return self._inner.get_extra_info(info)


class _GuardedBackend(httpcore.NetworkBackend):
    """Opens TCP connections only to checked addresses of the requested host.

    With a ``deadline`` (:func:`fetch`), the lookup, the connection and every
    read and write of its stream end by it: a request the caller was told had
    timed out is never sent afterwards.
    """

    def __init__(
        self, allowed_origins: frozenset[Origin], deadline: _Deadline | None = None
    ) -> None:
        self._allowed_origins = allowed_origins
        self._deadline = deadline
        self._inner = httpcore.SyncBackend()

    def _bound(self, timeout: float | None) -> float | None:
        return timeout if self._deadline is None else self._deadline.bound(timeout)

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.NetworkStream:
        addresses = resolve_public(
            host,
            port,
            allowed_origins=self._allowed_origins,
            timeout=self._bound(RESOLVE_TIMEOUT_SECONDS) or RESOLVE_TIMEOUT_SECONDS,
        )
        last: Exception | None = None
        for address in addresses:
            try:
                stream = self._inner.connect_tcp(
                    address,
                    port,
                    timeout=self._bound(timeout),
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last = exc
                continue
            if self._deadline is None:
                return stream
            return _DeadlineStream(stream, self._deadline)
        assert last is not None
        raise last

    def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.NetworkStream:
        raise _refused(UNIX_SOCKET)

    def sleep(self, seconds: float) -> None:
        self._inner.sleep(seconds)


# Async lookups wait in threads of their own pool: a host whose name service
# stalls takes these slots, never the default thread pool's (which the web
# framework uses for its sync code).
_RESOLVE_LIMITER = anyio.CapacityLimiter(16)


class _AsyncGuardedBackend(httpcore.AsyncNetworkBackend):
    """Async twin of :class:`_GuardedBackend`; the lookup runs in a thread."""

    def __init__(self, allowed_origins: frozenset[Origin]) -> None:
        self._allowed_origins = allowed_origins
        self._inner = httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        allowed = self._allowed_origins
        addresses = await anyio.to_thread.run_sync(
            lambda: resolve_public(host, port, allowed_origins=allowed),
            abandon_on_cancel=True,
            limiter=_RESOLVE_LIMITER,
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
        raise _refused(UNIX_SOCKET)

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


class GuardedTransport(httpx.HTTPTransport):
    """httpx transport whose connections go through :class:`_GuardedBackend`."""

    def __init__(
        self,
        *,
        allowed_origins: Iterable[str] | None = None,
        _deadline: _Deadline | None = None,
    ) -> None:
        super().__init__(trust_env=False)
        self._pool = httpcore.ConnectionPool(
            ssl_context=httpx.create_ssl_context(),
            network_backend=_GuardedBackend(parse_origins(allowed_origins), _deadline),
            http1=True,
            http2=False,
        )


class AsyncGuardedTransport(httpx.AsyncHTTPTransport):
    """Async httpx transport whose connections are checked the same way."""

    def __init__(self, *, allowed_origins: Iterable[str] | None = None) -> None:
        super().__init__(trust_env=False)
        self._pool = httpcore.AsyncConnectionPool(  # type: ignore[assignment]
            ssl_context=httpx.create_ssl_context(),
            network_backend=_AsyncGuardedBackend(parse_origins(allowed_origins)),
            http1=True,
            http2=False,
        )


_FORCED = ("transport", "mounts", "proxy", "proxies", "trust_env", "app")


def _client_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    for key in _FORCED:
        if key in kwargs:
            raise TypeError(f"guarded clients do not take {key!r}")
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT_SECONDS)
    kwargs.setdefault("max_redirects", DEFAULT_MAX_REDIRECTS)
    return kwargs


def client(
    *, allowed_origins: Iterable[str] | None = None, **kwargs: Any
) -> httpx.Client:
    """An ``httpx.Client`` that only reaches public addresses (see module doc)."""
    return httpx.Client(
        transport=GuardedTransport(allowed_origins=allowed_origins),
        trust_env=False,
        **_client_kwargs(kwargs),
    )


def async_client(
    *, allowed_origins: Iterable[str] | None = None, **kwargs: Any
) -> httpx.AsyncClient:
    """An ``httpx.AsyncClient`` that only reaches public addresses."""
    return httpx.AsyncClient(
        transport=AsyncGuardedTransport(allowed_origins=allowed_origins),
        trust_env=False,
        **_client_kwargs(kwargs),
    )


@dataclass(frozen=True)
class FetchedResponse:
    """A response read through :func:`fetch`, body capped at ``max_bytes``."""

    url: str
    status_code: int
    headers: Mapping[str, str]
    content: bytes
    truncated: bool

    @property
    def content_type(self) -> str:
        """Media type of the body, lower-case, without parameters."""
        return (self.headers.get("content-type") or "").split(";")[0].strip().lower()

    @property
    def charset(self) -> str | None:
        for part in (self.headers.get("content-type") or "").split(";")[1:]:
            key, _, value = part.partition("=")
            if key.strip().lower() == "charset" and value.strip():
                return value.strip().strip("\"'")
        return None

    def text(self) -> str:
        """Body decoded with its declared charset, or UTF-8."""
        try:
            return self.content.decode(self.charset or "utf-8", errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")


class _CappedBody:
    """Collects a body up to ``max_bytes``."""

    def __init__(self, max_bytes: int) -> None:
        self._max_bytes = max_bytes
        self._chunks: list[bytes] = []
        self._size = 0
        self.truncated = False

    def add(self, chunk: bytes) -> bool:
        """Keep ``chunk``; False once the cap is reached and reading should stop."""
        room = self._max_bytes - self._size
        if len(chunk) > room:
            self._chunks.append(chunk[:room])
            self._size = self._max_bytes
            self.truncated = True
            return False
        self._chunks.append(chunk)
        self._size += len(chunk)
        return True

    def response(self, response: httpx.Response) -> FetchedResponse:
        return FetchedResponse(
            url=str(response.url),
            status_code=response.status_code,
            headers=dict(response.headers),
            content=b"".join(self._chunks),
            truncated=self.truncated,
        )


@contextmanager
def _outbound_errors() -> Iterator[None]:
    """Turn transport failures into :class:`OutboundError` with fixed messages."""
    try:
        yield
    except OutboundError:
        raise
    except httpx.TooManyRedirects as exc:
        raise OutboundError("too many redirects") from exc
    except httpx.UnsupportedProtocol as exc:
        raise _refused(SCHEME) from exc
    except httpx.TimeoutException as exc:
        raise OutboundError(_TIMED_OUT) from exc
    except (httpx.HTTPError, httpx.InvalidURL, OSError) as exc:
        raise OutboundError("the host could not be reached") from exc


def _exchange(
    http: httpx.Client, url: str, headers: Mapping[str, str] | None, max_bytes: int
) -> FetchedResponse:
    body = _CappedBody(max_bytes)
    with (
        _outbound_errors(),
        http.stream("GET", url.strip(), headers=dict(headers or {})) as response,
    ):
        for chunk in response.iter_bytes():
            if not body.add(chunk):
                break
        return body.response(response)


def fetch(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    allowed_origins: Iterable[str] | None = None,
) -> FetchedResponse:
    """GET ``url`` through the guarded client, following checked redirects.

    Reads at most ``max_bytes`` of the body (``truncated`` says whether there
    was more). ``timeout`` bounds the whole exchange: lookups, connections,
    headers, every redirect hop and the body. Any status is returned; the
    caller decides what a 404 means.

    Raises :class:`OutboundRefused` when the URL or a destination is not
    allowed, and :class:`OutboundError` for every other failure.
    """
    check_url(url, allowed_origins=allowed_origins)
    deadline = _Deadline(timeout)
    http = httpx.Client(
        transport=GuardedTransport(allowed_origins=allowed_origins, _deadline=deadline),
        trust_env=False,
        timeout=timeout,
        follow_redirects=True,
        max_redirects=max_redirects,
    )
    outcome: dict[str, Any] = {}

    def run() -> None:
        try:
            outcome["response"] = _exchange(http, url, headers, max_bytes)
        except BaseException as exc:  # noqa: BLE001 - handed to the caller
            outcome["error"] = exc

    worker = threading.Thread(target=run, name="outbound-fetch", daemon=True)
    worker.start()
    worker.join(timeout)
    timed_out = worker.is_alive()
    # The worker stops on its own at the deadline (the backend and its streams
    # refuse past it); closing the pool also ends a read that is under way.
    http.close()
    if timed_out:
        raise OutboundError(_TIMED_OUT)
    if "error" in outcome:
        raise outcome["error"]
    return outcome["response"]


async def afetch(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    allowed_origins: Iterable[str] | None = None,
) -> FetchedResponse:
    """Async :func:`fetch`, with the same checks and limits."""
    check_url(url, allowed_origins=allowed_origins)
    body = _CappedBody(max_bytes)
    try:
        with anyio.fail_after(timeout), _outbound_errors():
            async with (
                async_client(
                    allowed_origins=allowed_origins,
                    timeout=timeout,
                    follow_redirects=True,
                    max_redirects=max_redirects,
                ) as http,
                http.stream(
                    "GET", url.strip(), headers=dict(headers or {})
                ) as response,
            ):
                async for chunk in response.aiter_bytes():
                    if not body.add(chunk):
                        break
                return body.response(response)
    except TimeoutError as exc:
        raise OutboundError(_TIMED_OUT) from exc
