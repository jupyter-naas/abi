"""{{integration_name_pascal}}Integration: a way to reach a third-party tool.

Written like an in-engine integration, on ``naas_abi_sdk`` only. Nothing in the
engine consumes it: a module's workflows, pipelines and agents build it and call
it. Fetch the credentials from the engine's secret service (declare it in
``ModuleDependencies(services=("secret",))``) and pass them in:

    key = await self.engine.services.secret.get("{{integration_name_upper}}_API_KEY")
    api = {{integration_name_pascal}}Integration(
        {{integration_name_pascal}}IntegrationConfiguration(api_key=key)
    )

A workflow reads them in its ``New(module)``. Use an async HTTP client (httpx), and
raise ``IntegrationConnectionError`` when the tool cannot be reached.
"""

from __future__ import annotations

from dataclasses import dataclass

from naas_abi_sdk.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)


@dataclass
class {{integration_name_pascal}}IntegrationConfiguration(IntegrationConfiguration):
    """Credentials and settings for the {{integration_name_pascal}} integration."""

    api_key: str = ""
    base_url: str = "https://api.example.com"


class {{integration_name_pascal}}Integration(Integration):
    """{{integration_name_pascal}} integration."""

    __configuration: {{integration_name_pascal}}IntegrationConfiguration

    def __init__(self, configuration: {{integration_name_pascal}}IntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    async def ping(self) -> str:
        """Replace with a call to the third-party API."""
        if not self.__configuration.api_key:
            raise IntegrationConnectionError(
                "{{integration_name_pascal}}: no API key in its configuration"
            )
        return self.__configuration.base_url
