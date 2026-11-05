"""Async HTTP for the integrations (``httpx``: in each application's extra)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
from naas_abi_sdk.integration import (
    IntegrationConfiguration,
    IntegrationConnectionError,
)


@dataclass(kw_only=True)
class HttpConfiguration(IntegrationConfiguration):
    """timeout: seconds per request. transport: an httpx transport (tests use
    ``httpx.MockTransport``)."""

    timeout: float = 60.0
    transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False)


async def request(
    configuration: HttpConfiguration,
    method: str,
    url: str,
    *,
    service: str,
    raise_for_status: bool = True,
    **kwargs: Any,
) -> httpx.Response:
    """One request; any HTTP failure is an ``IntegrationConnectionError``
    (``raise_for_status=False``: an error status is returned, not raised)."""
    try:
        async with httpx.AsyncClient(
            timeout=configuration.timeout, transport=configuration.transport
        ) as client:
            response = await client.request(method, url, **kwargs)
            if raise_for_status:
                response.raise_for_status()
            return response
    except httpx.HTTPError as exc:
        raise IntegrationConnectionError(
            f"{service} API request failed: {exc!s}"
        ) from exc


async def request_json(
    configuration: HttpConfiguration,
    method: str,
    url: str,
    *,
    service: str,
    **kwargs: Any,
) -> Any:
    response = await request(configuration, method, url, service=service, **kwargs)
    return response.json()
