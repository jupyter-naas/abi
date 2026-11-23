"""The guarded outbound client reaches public addresses only.

Every test runs against listeners on 127.0.0.1. A test that needs a "public"
host either lists its 127.0.0.1 origin in ``allowed_origins`` (the deployment's own list)
or answers a public address from a patched resolver and routes the connection
to the listener, recording which address the client asked for.
"""

from __future__ import annotations

import asyncio
import socket
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpcore
import pytest

from naas_abi_core.utils import outbound
from naas_abi_core.utils.outbound import OutboundError, OutboundRefused

LOOPBACK = "127.0.0.1"
PUBLIC = "93.184.216.34"


class _Server:
    def __init__(self) -> None:
        self.hits: list[tuple[str, str]] = []
        self.redirect_to = ""
        self.body = b"listener body"
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                server.hits.append((self.path, self.headers.get("Host", "")))
                if self.path.startswith("/redirect"):
                    self.send_response(302)
                    self.send_header("Location", server.redirect_to)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(server.body)))
                self.end_headers()
                self.wfile.write(server.body)

            def log_message(self, *args: object) -> None:
                pass

        self._httpd = ThreadingHTTPServer((LOOPBACK, 0), Handler)
        self.port = self._httpd.server_address[1]
        threading.Thread(
            target=self._httpd.serve_forever, args=(0.05,), daemon=True
        ).start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


@pytest.fixture
def server() -> Iterator[_Server]:
    srv = _Server()
    yield srv
    srv.close()


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "127.1",
        "2130706433",
        "0x7f000001",
        "localhost",
        "localhost.",
        "[::1]",
        "[::ffff:127.0.0.1]",
        "fuseki",
        "api.localhost",
        "minio.local",
        "metadata.google.internal",
    ],
)
def test_outbound_fetch_keeps_requests_off_internal_addresses(
    server: _Server, host: str
) -> None:
    with pytest.raises(OutboundRefused):
        outbound.fetch(f"http://{host}:{server.port}/secret", timeout=5)
    assert server.hits == []


def test_outbound_fetch_keeps_names_resolving_inside_off_limits(
    server: _Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = socket.getaddrinfo

    def resolver(host, *args, **kwargs):  # type: ignore[no-untyped-def]
        if host == "fuseki.example.com":
            host = LOOPBACK
        return real(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", resolver)
    with pytest.raises(OutboundRefused):
        outbound.fetch(f"http://fuseki.example.com:{server.port}/secret", timeout=5)
    assert server.hits == []


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.1.2.3",
        "172.16.0.1",
        "192.168.1.1",
        "100.64.0.1",
        "169.254.169.254",
        "0.0.0.0",  # nosec B104 - an address the check refuses, not a bind
        "224.0.0.1",
        "255.255.255.255",
        "::1",
        "::",
        "fe80::1",
        "fd00:ec2::254",
        "::ffff:127.0.0.1",
        "2002:7f00:1::",
        "64:ff9b::a00:1",
        "ff02::1",
    ],
)
def test_outbound_address_check_keeps_non_public_addresses_out(address: str) -> None:
    assert outbound.address_refusal(address) is not None


@pytest.mark.parametrize(
    "address",
    [
        "93.184.216.34",
        "8.8.8.8",
        "2606:4700::1111",
        "::ffff:8.8.8.8",
        "64:ff9b::808:808",
        "2002:808:808::",
    ],
)
def test_outbound_address_check_keeps_public_addresses_in(address: str) -> None:
    assert outbound.address_refusal(address) is None


def test_outbound_fetch_keeps_the_checked_address(
    server: _Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The name is resolved once; the connection goes to the address checked.

    The resolver answers a public address first and loopback afterwards. The
    connection must go to the public address (routed here to the listener),
    and the request must still carry the name in its Host header.
    """
    real = socket.getaddrinfo
    lookups: list[str] = []

    def resolver(host, port, *args, **kwargs):  # type: ignore[no-untyped-def]
        if host == "images.example.com":
            lookups.append(host)
            ip = PUBLIC if len(lookups) == 1 else LOOPBACK
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]
        return real(host, port, *args, **kwargs)

    connected: list[str] = []
    real_connect = httpcore.SyncBackend.connect_tcp

    def connect(self, host, port, *args, **kwargs):  # type: ignore[no-untyped-def]
        connected.append(host)
        target = LOOPBACK if host == PUBLIC else host
        return real_connect(self, target, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", resolver)
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", connect)

    response = outbound.fetch(f"http://images.example.com:{server.port}/a", timeout=5)

    assert response.status_code == 200
    assert response.content == server.body
    assert lookups == ["images.example.com"]
    assert connected == [PUBLIC]
    assert server.hits == [("/a", f"images.example.com:{server.port}")]


def test_outbound_fetch_keeps_every_redirect_hop_checked(server: _Server) -> None:
    server.redirect_to = f"http://localhost:{server.port}/secret"
    with pytest.raises(OutboundRefused):
        outbound.fetch(
            f"http://{LOOPBACK}:{server.port}/redirect",
            allowed_origins=[f"{LOOPBACK}:{server.port}"],
            timeout=5,
        )
    assert [path for path, _ in server.hits] == ["/redirect"]


def test_outbound_fetch_keeps_redirects_on_http(server: _Server) -> None:
    ftp = socket.socket()
    ftp.bind((LOOPBACK, 0))
    ftp.listen(1)
    ftp.settimeout(0.5)
    server.redirect_to = f"ftp://{LOOPBACK}:{ftp.getsockname()[1]}/x.png"
    try:
        with pytest.raises(OutboundRefused):
            outbound.fetch(
                f"http://{LOOPBACK}:{server.port}/redirect",
                allowed_origins=[f"{LOOPBACK}:{server.port}"],
                timeout=5,
            )
        with pytest.raises(OSError):
            ftp.accept()
    finally:
        ftp.close()


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/x",
        "file:///etc/passwd",
        "data:text/plain,hi",
        "gopher://example.com/",
    ],
)
def test_outbound_fetch_keeps_to_http_and_https(url: str) -> None:
    with pytest.raises(OutboundRefused):
        outbound.fetch(url)


def test_outbound_fetch_keeps_proxy_settings_out(
    server: _Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    proxy = _Server()
    try:
        for var in ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
            monkeypatch.setenv(var, f"http://{LOOPBACK}:{proxy.port}")
        monkeypatch.delenv("NO_PROXY", raising=False)
        monkeypatch.delenv("no_proxy", raising=False)
        response = outbound.fetch(
            f"http://{LOOPBACK}:{server.port}/a",
            allowed_origins=[f"{LOOPBACK}:{server.port}"],
            timeout=5,
        )
        assert response.status_code == 200
        assert proxy.hits == []
    finally:
        proxy.close()


def test_outbound_fetch_keeps_bodies_within_the_cap(server: _Server) -> None:
    server.body = b"x" * 10_000
    response = outbound.fetch(
        f"http://{LOOPBACK}:{server.port}/big",
        allowed_origins=[f"{LOOPBACK}:{server.port}"],
        max_bytes=1_000,
        timeout=5,
    )
    assert response.truncated is True
    assert len(response.content) == 1_000


def test_outbound_fetch_keeps_listed_hosts_reachable(server: _Server) -> None:
    response = outbound.fetch(
        f"http://{LOOPBACK}:{server.port}/ok",
        allowed_origins=[f"{LOOPBACK}:{server.port}"],
        timeout=5,
    )
    assert response.status_code == 200
    assert response.truncated is False
    assert response.text() == "listener body"
    assert response.content_type == "text/plain"


def test_outbound_fetch_keeps_too_many_redirects_an_error(server: _Server) -> None:
    server.redirect_to = f"http://{LOOPBACK}:{server.port}/redirect"
    with pytest.raises(OutboundError):
        outbound.fetch(
            f"http://{LOOPBACK}:{server.port}/redirect",
            allowed_origins=[f"{LOOPBACK}:{server.port}"],
            max_redirects=2,
            timeout=5,
        )


def test_outbound_async_fetch_keeps_requests_off_internal_addresses(
    server: _Server,
) -> None:
    with pytest.raises(OutboundRefused):
        asyncio.run(outbound.afetch(f"http://127.1:{server.port}/secret", timeout=5))
    server.redirect_to = f"http://localhost:{server.port}/secret"
    with pytest.raises(OutboundRefused):
        asyncio.run(
            outbound.afetch(
                f"http://{LOOPBACK}:{server.port}/redirect",
                allowed_origins=[f"{LOOPBACK}:{server.port}"],
                timeout=5,
            )
        )
    assert [path for path, _ in server.hits] == ["/redirect"]


def test_outbound_async_fetch_keeps_the_checked_address(
    server: _Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = socket.getaddrinfo
    lookups: list[str] = []

    def resolver(host, port, *args, **kwargs):  # type: ignore[no-untyped-def]
        if host == "images.example.com":
            lookups.append(host)
            ip = PUBLIC if len(lookups) == 1 else LOOPBACK
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]
        return real(host, port, *args, **kwargs)

    connected: list[str] = []
    real_connect = httpcore.AnyIOBackend.connect_tcp

    async def connect(self, host, port, *args, **kwargs):  # type: ignore[no-untyped-def]
        connected.append(host)
        target = LOOPBACK if host == PUBLIC else host
        return await real_connect(self, target, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", resolver)
    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", connect)

    response = asyncio.run(
        outbound.afetch(f"http://images.example.com:{server.port}/a", timeout=5)
    )

    assert response.content == server.body
    assert lookups == ["images.example.com"]
    assert connected == [PUBLIC]


def test_outbound_clients_keep_their_transport() -> None:
    for forced in ("transport", "proxy", "trust_env", "mounts"):
        with pytest.raises(TypeError):
            outbound.client(**{forced: None})


class _TrickleServer:
    """Answers a status line, then one header byte every ``pause`` seconds."""

    def __init__(self, pause: float = 0.2) -> None:
        self._sock = socket.socket()
        self._sock.bind((LOOPBACK, 0))
        self._sock.listen(4)
        self.port = self._sock.getsockname()[1]
        self._pause = pause
        self._stop = threading.Event()
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            threading.Thread(target=self._trickle, args=(conn,), daemon=True).start()

    def _trickle(self, conn: socket.socket) -> None:
        try:
            conn.recv(4096)
            conn.sendall(b"HTTP/1.1 200 OK\r\n")
            while not self._stop.is_set():
                conn.sendall(b"X")
                time.sleep(self._pause)
        except OSError:
            pass
        finally:
            conn.close()

    def close(self) -> None:
        self._stop.set()
        self._sock.close()


@pytest.fixture
def trickle() -> Iterator[_TrickleServer]:
    srv = _TrickleServer()
    yield srv
    srv.close()


def test_outbound_fetch_keeps_one_deadline_over_the_whole_exchange(
    trickle: _TrickleServer,
) -> None:
    started = time.monotonic()
    with pytest.raises(OutboundError):
        outbound.fetch(
            f"http://{LOOPBACK}:{trickle.port}/slow",
            allowed_origins=[f"{LOOPBACK}:{trickle.port}"],
            timeout=1.0,
        )
    assert time.monotonic() - started < 3.0


def test_outbound_async_fetch_keeps_one_deadline_over_the_whole_exchange(
    trickle: _TrickleServer,
) -> None:
    started = time.monotonic()
    with pytest.raises(OutboundError):
        asyncio.run(
            outbound.afetch(
                f"http://{LOOPBACK}:{trickle.port}/slow",
                allowed_origins=[f"{LOOPBACK}:{trickle.port}"],
                timeout=1.0,
            )
        )
    assert time.monotonic() - started < 3.0


def test_outbound_lookup_keeps_to_its_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    def hanging(*args, **kwargs):  # type: ignore[no-untyped-def]
        time.sleep(5)
        return []

    monkeypatch.setattr(socket, "getaddrinfo", hanging)
    started = time.monotonic()
    with pytest.raises(OutboundError):
        outbound.resolve_public("slow.example.com", 80, timeout=0.5)
    assert time.monotonic() - started < 2.0


@pytest.mark.parametrize(
    "url",
    [
        "http://[::1",
        "http://[x/",
        "http://example.com:99999/",
        "http://example.com:port/",
    ],
)
def test_outbound_fetch_keeps_unparsable_urls_refused(url: str) -> None:
    with pytest.raises(OutboundRefused) as info:
        outbound.fetch(url)
    assert info.value.reason in {outbound.INVALID_URL, outbound.NO_HOST}


def test_outbound_origins_keep_other_ports_of_a_listed_host_checked(
    server: _Server,
) -> None:
    other = _Server()
    try:
        allowed = [f"{LOOPBACK}:{server.port}"]
        assert (
            outbound.fetch(
                f"http://{LOOPBACK}:{server.port}/ok",
                allowed_origins=allowed,
                timeout=5,
            ).status_code
            == 200
        )
        with pytest.raises(OutboundRefused):
            outbound.fetch(
                f"http://{LOOPBACK}:{other.port}/x", allowed_origins=allowed, timeout=5
            )
        server.redirect_to = f"http://{LOOPBACK}:{other.port}/x"
        with pytest.raises(OutboundRefused):
            outbound.fetch(
                f"http://{LOOPBACK}:{server.port}/redirect",
                allowed_origins=allowed,
                timeout=5,
            )
        assert other.hits == []
    finally:
        other.close()


@pytest.mark.parametrize(
    ("entries", "expected"),
    [
        (["abi:9879"], {("abi", 9879)}),
        (["http://Abi:9879/"], {("abi", 9879)}),
        (["https://gateway.example"], {("gateway.example", 443)}),
        (["gateway.example"], {("gateway.example", 80), ("gateway.example", 443)}),
        (["[::1]:8080"], {("::1", 8080)}),
        (["", "http://[x"], set()),
    ],
)
def test_outbound_origins_keep_host_and_port(entries: list[str], expected: set) -> None:
    assert outbound.parse_origins(entries) == expected


def test_outbound_fetch_keeps_a_timed_out_request_unsent(
    server: _Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lookup that outlasts the deadline never turns into a request."""
    real = socket.getaddrinfo

    def slow(host, port, *args, **kwargs):  # type: ignore[no-untyped-def]
        if host == "slow.example.com":
            time.sleep(1.5)
            host = LOOPBACK
        return real(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", slow)
    started = time.monotonic()
    with pytest.raises(OutboundError):
        outbound.fetch(
            f"http://slow.example.com:{server.port}/late",
            allowed_origins=[f"slow.example.com:{server.port}"],
            timeout=0.5,
        )
    assert time.monotonic() - started < 1.0
    time.sleep(1.5)  # the lookup has answered by now
    assert server.hits == []


class _TrickleBody:
    """Sends headers announcing a large body, then one byte every ``pause``."""

    def __init__(self, pause: float = 0.1) -> None:
        self._sock = socket.socket()
        self._sock.bind((LOOPBACK, 0))
        self._sock.listen(1)
        self.port = self._sock.getsockname()[1]
        self._pause = pause
        self.closed_at: float | None = None
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        try:
            conn, _ = self._sock.accept()
        except OSError:
            return
        try:
            conn.recv(4096)
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 1000000\r\n\r\n")
            while True:
                conn.sendall(b"x")
                time.sleep(self._pause)
        except OSError:
            self.closed_at = time.monotonic()
        finally:
            conn.close()

    def close(self) -> None:
        self._sock.close()


def test_outbound_fetch_keeps_a_trickled_body_to_the_deadline() -> None:
    body = _TrickleBody()
    try:
        started = time.monotonic()
        with pytest.raises(OutboundError):
            outbound.fetch(
                f"http://{LOOPBACK}:{body.port}/slow",
                allowed_origins=[f"{LOOPBACK}:{body.port}"],
                timeout=1.0,
            )
        assert time.monotonic() - started < 1.5
        # The connection is closed by the deadline: the server's sends fail.
        for _ in range(30):
            if body.closed_at is not None:
                break
            time.sleep(0.1)
        assert body.closed_at is not None
        assert body.closed_at - started < 2.5
    finally:
        body.close()


def test_outbound_async_lookups_keep_out_of_the_default_thread_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import anyio
    import anyio.to_thread

    real = socket.getaddrinfo

    def stalled(host, port, *args, **kwargs):  # type: ignore[no-untyped-def]
        if host.endswith(".stalled.example.com"):
            time.sleep(1.0)
        return real(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", stalled)

    async def main() -> int:
        default = anyio.to_thread.current_default_thread_limiter()

        async def one(n: int) -> None:
            with pytest.raises(OutboundError):
                await outbound.afetch(f"http://h{n}.stalled.example.com/", timeout=0.5)

        async with anyio.create_task_group() as tasks:
            for n in range(8):
                tasks.start_soon(one, n)
            await anyio.sleep(0.2)
            borrowed = default.borrowed_tokens
        return borrowed

    assert asyncio.run(main()) == 0
