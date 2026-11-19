"""HTTP errors never carry a URL's query string: some APIs take their key there,
and the error reaches the model and the logs."""

from __future__ import annotations

import asyncio
import logging

import httpx
import pytest
from naas_abi_apps.common.http import HttpConfiguration, redact_url, request
from naas_abi_apps.common.runtime import quiet_http_logs
from naas_abi_sdk.integration import IntegrationConnectionError


def configuration(handler) -> HttpConfiguration:
    return HttpConfiguration(transport=httpx.MockTransport(handler))


def test_redact_url_drops_query_and_user_info() -> None:
    assert (
        redact_url("https://u:p@api.x.io/v1/latest?access_key=SECRET&base=EUR#f")
        == "https://api.x.io/v1/latest"
    )


def test_an_error_status_names_the_url_without_its_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid key"})

    with pytest.raises(IntegrationConnectionError) as raised:
        asyncio.run(
            request(
                configuration(handler),
                "GET",
                "https://api.x.io/v1/latest",
                service="X",
                params={"access_key": "SECRET"},
            )
        )

    message = str(raised.value)
    assert message == (
        "X API request failed: 401 Unauthorized for GET https://api.x.io/v1/latest"
    )
    # Not chained: a logged traceback would print the httpx error, URL included.
    assert raised.value.__cause__ is None and raised.value.__suppress_context__


def test_a_transport_error_names_the_url_without_its_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot reach {request.url}", request=request)

    with pytest.raises(IntegrationConnectionError) as raised:
        asyncio.run(
            request(
                configuration(handler),
                "GET",
                "https://api.x.io/v1?key=SECRET",
                service="X",
            )
        )

    assert "SECRET" not in str(raised.value)
    assert "ConnectError for GET https://api.x.io/v1" in str(raised.value)


def test_httpx_request_logs_stay_quiet() -> None:
    logging.getLogger("httpx").setLevel(logging.NOTSET)

    quiet_http_logs()

    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)
    assert not logging.getLogger("httpcore").isEnabledFor(logging.DEBUG)
