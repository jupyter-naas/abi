"""A remote module's app through Nexus, end to end, as a browser uses it.

A real broker logged in as deployed (Nexus as ``abi``, the module as
``module``), the engine's discovery, an SDK module serving an app with files
and a backend, and Nexus's remote app routes on a real HTTP server. The
browser opens the app under a grant, calls its backend, uploads, reads a
stream that breaks off, and loses the app at logout.
"""

from __future__ import annotations

import asyncio
import json
import socket
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

pytest.importorskip("naas_abi_sdk")
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from naas_abi_core.engine.nats_test_server import (  # noqa: E402
    login,
    native_nats_server,
    nats_server_binary,
)

SECRET = "remote-apps-integration-test-secret-32b"
PASSWORDS = {"abi": "nats-abi-remote-apps", "module": "nats-module-remote-apps"}
MB = 1024 * 1024
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(nats_server_binary() is None, reason="nats-server not installed"),
]


@pytest.fixture
def broker(tmp_path):
    with native_nats_server(tmp_path, jetstream=True, users=PASSWORDS) as url:
        yield login(url, "abi", PASSWORDS["abi"]), login(url, "module", PASSWORDS["module"])


def _backend() -> FastAPI:
    api = FastAPI()

    @api.get("/api/whoami")
    async def whoami(request: Request):
        return request.scope["abi"]

    @api.put("/api/upload")
    async def upload(request: Request):
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
        return {"size": size}

    @api.get("/api/export")
    async def export():
        async def rows():
            yield b"x" * MB
            raise RuntimeError("the export's source went away")

        return StreamingResponse(rows(), headers={"content-length": str(3 * MB)})

    return api


def test_a_browser_uses_a_remote_app_through_nexus(broker, tmp_path, monkeypatch):
    import httpx
    import uvicorn
    from naas_abi.apps.nexus.apps.api.app.services.apps.remote import http_routes as http
    from naas_abi.apps.nexus.apps.api.app.services.apps.remote.factory import (
        build_remote_app_directory,
    )
    from naas_abi_core.engine.nats_auth import module_key
    from naas_abi_core.services.discovery.discovery_factory import start_discovery
    from naas_abi_sdk import BaseModule, DiscoveryConfiguration, run_module
    from naas_abi_sdk.apps import AppDescriptor
    from naas_abi_sdk.service_token import ModuleToken

    engine, module = broker
    site = tmp_path / "console"
    site.mkdir()
    (site / "index.html").write_text("<h1>console</h1>")

    class Console(BaseModule):
        module_id = "acme.console"
        apps = (AppDescriptor("console", "Console", root=site),)

        async def on_initialized(self):
            self.expose_app("console", _backend())

        async def run(self):
            await asyncio.Event().wait()

    # Nexus: its directory over the broker, without a database (no logout yet).
    directory = build_remote_app_directory(
        SimpleNamespace(
            nats_url=engine, jwt_secret=SECRET, discovery=SimpleNamespace(project="default")
        )
    )
    logged_out: dict[str, datetime] = {}

    async def grant_revoked(user_id: str, issued_at: datetime) -> bool:
        return user_id in logged_out and logged_out[user_id] >= issued_at

    monkeypatch.setattr(http, "get_remote_app_directory", lambda: directory)
    monkeypatch.setattr(http, "current_secret_key", lambda: SECRET)
    monkeypatch.setattr(http.revocation, "grant_revoked", grant_revoked)
    nexus = FastAPI()
    nexus.add_api_route(
        "/app-remote/{grant}/{module_id}/{app}/{path:path}",
        http.serve_remote_app,
        methods=http.METHODS,
    )
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(nexus, host="127.0.0.1", port=port, log_level="critical")
    )

    async def scenario():
        import nats

        nc = await nats.connect(engine)
        registry = await start_discovery(nc, SECRET)
        running = asyncio.create_task(
            run_module(
                Console,
                url=module,
                token=ModuleToken("acme.console", module_key(SECRET, "acme.console")),
                discovery=DiscoveryConfiguration(),
            )
        )
        serving = asyncio.create_task(server.serve())
        try:
            while not server.started:
                await asyncio.sleep(0.02)
            for _ in range(200):  # READY in discovery
                if await directory.list_apps():
                    break
                await asyncio.sleep(0.05)
                directory._clients.clear()  # read discovery again
            root = f"http://127.0.0.1:{port}" + http.remote_app_grant_url(
                "u-1", "acme.console", "console", workspace_id="ws-1"
            )
            async with httpx.AsyncClient(timeout=10) as browser:
                page = await browser.get(root)
                assert (page.status_code, page.text) == (200, "<h1>console</h1>")
                assert page.headers["content-security-policy"] == http.SANDBOX

                whoami = await browser.get(f"{root}api/whoami")
                assert whoami.json() == {
                    "user_id": "u-1",
                    "workspace_id": "ws-1",
                    "caller": "api",
                }

                uploaded = await browser.put(f"{root}api/upload", content=b"u" * (3 * MB))
                assert uploaded.json() == {"size": 3 * MB}

                with pytest.raises(httpx.RemoteProtocolError):  # never a short "whole" file
                    await browser.get(f"{root}api/export")

                logged_out["u-1"] = datetime.now(UTC)
                after = await browser.get(f"{root}api/whoami")
                assert after.status_code == 401
                assert json.loads(after.text)["detail"].startswith("This app link has expired")
        finally:
            server.should_exit = True
            await serving
            running.cancel()
            await asyncio.gather(running, return_exceptions=True)
            await registry.stop()
            await nc.close()

    asyncio.run(scenario())
