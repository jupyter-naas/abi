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


def redact_url(url: httpx.URL | str) -> str:
    """``url`` without its query string or user info: some APIs take their
    key as a query parameter, and an error message reaches the model."""
    return str(httpx.URL(str(url)).copy_with(query=None, fragment=None, userinfo=b""))


def error_message(service: str, exc: httpx.HTTPError) -> str:
    """What failed, safe for the model and the logs: the status and the URL
    without its query (``str(exc)`` carries the full URL, keys included)."""
    try:
        full_url = str(exc.request.url)
        url, method = redact_url(full_url), exc.request.method
    except RuntimeError:  # raised before a request was built
        full_url, url, method = "", "", ""
    if isinstance(exc, httpx.HTTPStatusError):
        return (
            f"{service} API request failed: {exc.response.status_code} "
            f"{exc.response.reason_phrase} for {method} {url}"
        )
    detail = str(exc).replace(full_url, url) if full_url else str(exc)
    return f"{service} API request failed: {type(exc).__name__} for {method} {url}" + (
        f": {detail}" if detail else ""
    )


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
    (``raise_for_status=False``: an error status is returned, not raised).
    Its message never carries the query string (``error_message``), and the
    httpx exception is not chained: a logged traceback would print the URL."""
    try:
        async with httpx.AsyncClient(
            timeout=configuration.timeout, transport=configuration.transport
        ) as client:
            response = await client.request(method, url, **kwargs)
            if raise_for_status:
                response.raise_for_status()
            return response
    except httpx.HTTPError as exc:
        raise IntegrationConnectionError(error_message(service, exc)) from None


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
