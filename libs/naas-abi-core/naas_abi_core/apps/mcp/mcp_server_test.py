"""The MCP server acts only with the caller's own key, which Nexus checks, and
answers only the hosts and origins it is configured for."""

from __future__ import annotations

import importlib
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import ModuleType

import pytest
from starlette.testclient import TestClient

GOOD_KEY = "abi_pk_good"
DEPLOYMENT_KEY = "deployment-key-not-for-callers"
ACCEPT = "application/json, text/event-stream"


class Nexus(BaseHTTPRequestHandler):
    """The gateway: lists one agent and answers chats for GOOD_KEY only."""

    seen: list[tuple[str, str, str | None]] = []

    def log_message(self, *args: object) -> None:
        pass

    def _reply(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _allowed(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {GOOD_KEY}"

    def do_GET(self) -> None:
        Nexus.seen.append(("GET", self.path, self.headers.get("Authorization")))
        if not self._allowed():
            return self._reply(401, {"detail": "Not authenticated"})
        self._reply(200, {"data": [{"id": "Abi", "object": "model"}]})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        Nexus.seen.append(("POST", self.path, self.headers.get("Authorization")))
        if not self._allowed():
            return self._reply(401, {"detail": "Not authenticated"})
        self._reply(200, {"choices": [{"message": {"content": "agent answer"}}]})


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    nexus = ThreadingHTTPServer(("127.0.0.1", 0), Nexus)
    threading.Thread(target=nexus.serve_forever, daemon=True).start()
    Nexus.seen = []
    monkeypatch.setenv("ABI_API_BASE", f"http://127.0.0.1:{nexus.server_port}")
    monkeypatch.setenv("ABI_API_KEY", DEPLOYMENT_KEY)
    monkeypatch.setenv("MCP_HOST", "192.0.2.10")  # beyond loopback, as in a container
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("MCP_ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("NEXUS_ACCESS_TOKEN", raising=False)
    from naas_abi_core.apps.mcp import mcp_server

    # A fresh server per test: the module builds it from the environment.
    yield importlib.reload(mcp_server)
    nexus.shutdown()


def rpc(client: TestClient, headers: dict[str, str], method: str, params: dict) -> dict:
    """One MCP session: initialize, then ``method``; returns the last reply."""
    base = {"Accept": ACCEPT, "Content-Type": "application/json", **headers}
    init = client.post(
        "/mcp",
        headers=base,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        },
    )
    if init.status_code != 200:
        return {"status": init.status_code}
    session = {"mcp-session-id": init.headers["mcp-session-id"]}
    client.post(
        "/mcp",
        headers={**base, **session},
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    reply = client.post(
        "/mcp",
        headers={**base, **session},
        json={"jsonrpc": "2.0", "id": 2, "method": method, "params": params},
    )
    body = reply.text
    data = [line[5:].strip() for line in body.splitlines() if line.startswith("data:")]
    return {"status": reply.status_code, **(json.loads(data[-1]) if data else {})}


def ask(server: ModuleType, headers: dict[str, str], base_url: str) -> dict:
    with TestClient(server.mcp.streamable_http_app(), base_url=base_url) as client:
        return rpc(
            client,
            headers,
            "tools/call",
            {"name": "ask_agent", "arguments": {"agent": "Abi", "prompt": "hi"}},
        )


def test_mcp_server_keeps_requests_without_a_key_out(server: ModuleType) -> None:
    reply = ask(server, {}, "http://127.0.0.1:8000")

    assert reply["status"] == 401
    assert not [s for s in Nexus.seen if s[0] == "POST"]


def test_mcp_server_keeps_keys_nexus_refuses_out(server: ModuleType) -> None:
    reply = ask(server, {"Authorization": "Bearer abi_pk_bad"}, "http://127.0.0.1:8000")

    assert reply["status"] == 401
    assert not [s for s in Nexus.seen if s[0] == "POST"]


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "other.example.test:8000"},
        {"Host": "127.0.0.1:8000", "Origin": "http://other.example.test:8000"},
    ],
    ids=["host", "origin"],
)
def test_mcp_server_keeps_to_its_hosts_and_origins(
    server: ModuleType, headers: dict[str, str]
) -> None:
    reply = ask(
        server,
        {"Authorization": f"Bearer {GOOD_KEY}", **headers},
        f"http://{headers['Host']}",
    )

    assert reply["status"] in (403, 421)
    assert not [s for s in Nexus.seen if s[0] == "POST"]


def test_mcp_server_keeps_to_the_callers_key(server: ModuleType) -> None:
    reply = ask(
        server, {"Authorization": f"Bearer {GOOD_KEY}"}, "http://127.0.0.1:8000"
    )

    assert reply["status"] == 200
    assert reply["result"]["content"][0]["text"] == "agent answer"
    posts = [s for s in Nexus.seen if s[0] == "POST"]
    assert posts == [("POST", "/api/v1/chat/completions", f"Bearer {GOOD_KEY}")]
    assert all(DEPLOYMENT_KEY not in (s[2] or "") for s in Nexus.seen)


def test_mcp_server_configured_hosts_are_honoured(
    server: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "mcp.example.test:*")
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "https://app.example.test")
    module = importlib.reload(server)

    reply = ask(
        module,
        {"Authorization": f"Bearer {GOOD_KEY}", "Host": "mcp.example.test:8000"},
        "http://mcp.example.test:8000",
    )
    loopback = ask(
        importlib.reload(module),
        {"Authorization": f"Bearer {GOOD_KEY}"},
        "http://127.0.0.1:8000",
    )

    assert reply["status"] == 200
    assert loopback["status"] in (403, 421)


def test_mcp_server_keeps_its_public_address_explicit(server: ModuleType) -> None:
    assert server.http_transport_problem("127.0.0.1", "") is None
    assert server.http_transport_problem("192.0.2.10", "") is not None
    assert (
        server.http_transport_problem("192.0.2.10", "https://mcp.example.test") is None
    )


def test_mcp_key_cache_keeps_only_live_entries(
    server: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio

    verifier = server.NexusKeyVerifier()
    clock = [100.0]
    monkeypatch.setattr(server.time, "monotonic", lambda: clock[0])
    verifier._accepted = {"stale": 50.0}

    assert asyncio.run(verifier.verify_token(GOOD_KEY)) is not None
    assert "stale" not in verifier._accepted and len(verifier._accepted) == 1
