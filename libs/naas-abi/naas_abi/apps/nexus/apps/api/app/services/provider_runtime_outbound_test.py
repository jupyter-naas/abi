"""Provider calls: one guarded client, agent names as one path segment, tokens in headers."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from naas_abi.apps.nexus.apps.api.app.services import provider_runtime as pr
from naas_abi_core.utils.outbound import OutboundRefused


class _Listener:
    def __init__(self) -> None:
        self.hits: list[str] = []
        listener = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                listener.hits.append(self.path)
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                body = json.dumps({"completion": "listener answer"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: object) -> None:
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._httpd.server_address[1]}"
        threading.Thread(target=self._httpd.serve_forever, args=(0.05,), daemon=True).start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


@pytest.fixture
def listener() -> Iterator[_Listener]:
    srv = _Listener()
    yield srv
    srv.close()


@pytest.fixture
def platform_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pr, "resolve_endpoint", lambda: "http://ollama.platform:11434")


def _abi(endpoint: str, model: str, api_key: str | None = "SERVER-TOKEN") -> pr.ProviderConfig:
    return pr.ProviderConfig(
        id="abi-1",
        name="ABI",
        type="abi",
        enabled=True,
        endpoint=endpoint,
        api_key=api_key,
        model=model,
    )


def _recording_client(seen: list[httpx.Request]):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"completion": "ok"})

    return lambda timeout: httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_abi_server_call_keeps_the_agent_name_in_one_segment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []
    monkeypatch.setattr(pr, "provider_client", _recording_client(seen))

    await pr.complete_with_abi(
        [pr.Message(role="user", content="hi")],
        _abi("https://abi.example.com", "../../admin/users/delete?all=1&"),
        None,
        injection_preamble=None,
    )

    assert len(seen) == 1
    url = seen[0].url
    assert url.raw_path.startswith(b"/agents/")
    assert url.raw_path.endswith(b"/completion")
    assert url.raw_path.count(b"/") == 3
    assert url.query == b""
    assert seen[0].headers["Authorization"] == "Bearer SERVER-TOKEN"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["", ".", "..", "a\nb"])
async def test_abi_server_call_keeps_unusable_agent_names_out(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    seen: list[httpx.Request] = []
    monkeypatch.setattr(pr, "provider_client", _recording_client(seen))
    with pytest.raises(ValueError):
        await pr.complete_with_abi(
            [pr.Message(role="user", content="hi")],
            _abi("https://abi.example.com", name),
            None,
            injection_preamble=None,
        )
    assert seen == []


@pytest.mark.asyncio
async def test_abi_server_stream_keeps_the_token_in_a_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []
    monkeypatch.setattr(pr, "provider_client", _recording_client(seen))
    async for _ in pr.stream_with_abi(
        [pr.Message(role="user", content="hi")], _abi("https://abi.example.com", "a/b?c")
    ):
        pass
    assert len(seen) == 1
    assert seen[0].url.query == b""
    assert seen[0].url.raw_path == b"/agents/a%2Fb%3Fc/stream-completion"
    assert seen[0].headers["Authorization"] == "Bearer SERVER-TOKEN"


_REFUSED = (OutboundRefused, pr.UnsafeProviderEndpointError)


@pytest.mark.asyncio
async def test_provider_calls_keep_to_public_or_listed_origins(
    listener: _Listener, platform_ollama: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = pr.nexus_config.settings
    monkeypatch.setattr(settings, "provider_allowed_origins", [], raising=False)
    message = [pr.Message(role="user", content="hi")]

    with pytest.raises(_REFUSED):
        await pr.complete_with_abi(
            message, _abi(listener.url, "agent"), None, injection_preamble=None
        )
    custom = pr.ProviderConfig(
        id="c", name="c", type="ollama", enabled=True, endpoint=listener.url, model="m"
    )
    with pytest.raises(_REFUSED):
        await pr.complete_with_ollama(message, custom, None)
    # The listed host alone is not enough: the origin names the port.
    monkeypatch.setattr(settings, "provider_allowed_origins", ["127.0.0.1:1"], raising=False)
    with pytest.raises(_REFUSED):
        await pr.complete_with_abi(
            message, _abi(listener.url, "agent"), None, injection_preamble=None
        )
    assert listener.hits == []

    # An origin the deployment lists is reached, by its checked address.
    monkeypatch.setattr(settings, "provider_allowed_origins", [listener.url], raising=False)
    answer = await pr.complete_with_abi(
        message, _abi(listener.url, "agent"), None, injection_preamble=None
    )
    assert answer == "listener answer"
    assert listener.hits == ["/agents/agent/completion"]


@pytest.mark.asyncio
async def test_abi_server_keeps_off_the_ollama_hosts_other_ports(
    listener: _Listener, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The platform Ollama's origin opens nothing else on its host."""
    ollama = _Listener()
    try:
        monkeypatch.setattr(pr, "resolve_endpoint", lambda: ollama.url)
        monkeypatch.setattr(pr.nexus_config.settings, "provider_allowed_origins", [], raising=False)
        message = [pr.Message(role="user", content="hi")]

        # An ABI server on the Ollama host, at another port.
        with pytest.raises(_REFUSED):
            await pr.complete_with_abi(
                message, _abi(listener.url, "agent"), None, injection_preamble=None
            )
        # An ABI server set to the Ollama origin itself: not an Ollama call.
        with pytest.raises(_REFUSED):
            await pr.complete_with_abi(
                message, _abi(ollama.url, "agent"), None, injection_preamble=None
            )
        async with pr.provider_client(5.0) as client:
            with pytest.raises(OutboundRefused):
                await client.post(f"{ollama.url}/api/chat", json={})
        assert listener.hits == []
        assert ollama.hits == []

        # Ollama calls reach the platform Ollama.
        async with pr.provider_client(5.0, ollama=True) as client:
            answer = await client.post(f"{ollama.url}/api/chat", json={})
        assert answer.status_code == 200
        assert ollama.hits == ["/api/chat"]
    finally:
        ollama.close()


def test_provider_origins_keep_the_platform_ollama_to_ollama_calls(
    platform_ollama: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        pr.nexus_config.settings,
        "provider_allowed_origins",
        ["ABI-Server:9879", " "],
        raising=False,
    )
    assert pr.provider_origin_entries() == ["ABI-Server:9879"]
    assert pr.provider_origin_entries(ollama=True) == [
        "ABI-Server:9879",
        "http://ollama.platform:11434",
    ]


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (OutboundRefused("it does not resolve to a public address"), "not allowed"),
        (pr.UnsafeProviderEndpointError("x"), "not allowed"),
        (httpx.ConnectError("[Errno 111] Connection refused 10.0.0.4:8080"), "could not"),
        (RuntimeError("secret body from the provider"), "could not"),
    ],
)
def test_provider_errors_keep_their_details_in_the_log(exc: Exception, expected: str) -> None:
    message = pr.client_error_message(exc)
    assert expected in message
    assert str(exc) not in message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model", "path"),
    [
        ("@cf/facebook/bart-large-cnn", "/ai/run/@cf/facebook/bart-large-cnn"),
        ("@cf/meta/llama-3.1-8b-instruct", "/ai/run/@cf/meta/llama-3.1-8b-instruct"),
        ("meta/llama-3.1-8b-instruct", "/ai/run/@cf/meta/llama-3.1-8b-instruct"),
    ],
)
async def test_cloudflare_calls_keep_the_model_name_whole(
    monkeypatch: pytest.MonkeyPatch, model: str, path: str
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"result": {"response": "ok"}})

    monkeypatch.setattr(
        pr,
        "provider_client",
        lambda timeout, **_: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    config = pr.ProviderConfig(
        id="cf",
        name="Cloudflare",
        type="cloudflare",
        enabled=True,
        api_key="token",
        account_id="acct",
        model=model,
    )
    assert (
        await pr.complete_with_cloudflare([pr.Message(role="user", content="hi")], config, None)
        == "ok"
    )
    assert seen[0].url.path == f"/client/v4/accounts/acct{path}"
