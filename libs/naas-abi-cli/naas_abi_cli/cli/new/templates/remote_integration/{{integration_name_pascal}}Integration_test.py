from __future__ import annotations

import asyncio

import pytest
from naas_abi_sdk.integration import IntegrationConnectionError

from .{{integration_name_pascal}}Integration import (
    {{integration_name_pascal}}Integration,
    {{integration_name_pascal}}IntegrationConfiguration,
)


def test_the_integration_uses_its_configuration() -> None:
    integration = {{integration_name_pascal}}Integration(
        {{integration_name_pascal}}IntegrationConfiguration(api_key="k", base_url="https://x")
    )

    assert asyncio.run(integration.ping()) == "https://x"


def test_the_integration_refuses_to_run_without_credentials() -> None:
    integration = {{integration_name_pascal}}Integration({{integration_name_pascal}}IntegrationConfiguration())

    with pytest.raises(IntegrationConnectionError):
        asyncio.run(integration.ping())
