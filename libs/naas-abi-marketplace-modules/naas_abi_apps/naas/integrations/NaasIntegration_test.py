"""Offline tests of the Naas integration and storage: httpx MockTransport, fake S3."""

from __future__ import annotations

import asyncio
import json

import httpx
from naas_abi_apps.naas.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
    as_tools,
)
from naas_abi_apps.naas.integrations.NaasStorage import full_key, parse_credentials

CREDENTIALS = {
    "credentials": {
        "s3": {
            "endpoint_url": "s3://naas-bucket/ws-1/storage-a",
            "access_key_id": "AK",
            "secret_key": "SK",
            "session_token": "ST",
        }
    }
}


class FakeS3:
    def __init__(self) -> None:
        self.puts: list[dict] = []

    def put_object(self, **kwargs) -> None:
        self.puts.append(kwargs)


def test_get_requests_carry_the_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer k"
        assert request.url == "https://api.naas.ai/workspace/"
        return httpx.Response(200, json={"workspaces": []})

    integration = NaasIntegration(
        NaasIntegrationConfiguration(
            api_key="k", transport=httpx.MockTransport(handler)
        )
    )

    assert asyncio.run(integration.list_workspaces()) == {"workspaces": []}


def test_credentials_and_keys() -> None:
    credentials = parse_credentials(CREDENTIALS)
    assert (credentials.bucket_name, credentials.bucket_prefix) == (
        "naas-bucket",
        "ws-1/storage-a",
    )
    assert (
        full_key("ws-1/storage-a", "/logos/", "a.png") == "ws-1/storage-a/logos/a.png"
    )


def test_upload_asset_writes_to_storage_and_reuses_an_existing_asset(
    monkeypatch,
) -> None:
    s3 = FakeS3()
    from naas_abi_apps.naas.integrations import NaasStorage as storage_module

    monkeypatch.setattr(
        storage_module.NaasStorage, "_client", lambda self, credentials: s3
    )
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path.endswith("/storage/credentials/"):
            assert json.loads(request.content) == {"name": "storage-a"}
            return httpx.Response(200, json=CREDENTIALS)
        if request.method == "POST" and request.url.path.endswith("/asset/"):
            # The API answers an error status when the asset exists, naming its id.
            return httpx.Response(
                409, json={"error": {"message": "Asset already exists with id:'as-9'"}}
            )
        return httpx.Response(200, json={"asset": {"url": "https://naas.ai/a/as-9/"}})

    integration = NaasIntegration(
        NaasIntegrationConfiguration(
            api_key="k",
            workspace_id="ws-1",
            storage_name="storage-a",
            transport=httpx.MockTransport(handler),
        )
    )

    result = asyncio.run(
        integration.upload_asset(b"png", "logos", "a.png", return_url=True)
    )

    assert result == {"asset_url": "https://naas.ai/a/as-9"}
    assert s3.puts == [
        {"Bucket": "naas-bucket", "Key": "ws-1/storage-a/logos/a.png", "Body": b"png"}
    ]
    assert calls[-1] == "GET /workspace/ws-1/asset/as-9"


def test_tools() -> None:
    tools = as_tools(NaasIntegrationConfiguration(api_key="k"))
    assert len(tools) == 32 and all(t.coroutine is not None for t in tools)
