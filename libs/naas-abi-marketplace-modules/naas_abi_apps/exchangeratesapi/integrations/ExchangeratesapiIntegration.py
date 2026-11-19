"""exchangeratesapi.io (FX rates), async, on ``naas_abi_sdk`` only.

Port of ``naas_abi_marketplace.applications.exchangeratesapi.integrations``:
same endpoints and tool names. The symbol list is kept in memory once read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from naas_abi_apps.common.http import HttpConfiguration, request
from naas_abi_sdk.integration import Integration

SERVICE = "Exchangeratesapi"


@dataclass
class ExchangeratesapiIntegrationConfiguration(HttpConfiguration):
    api_key: str
    base_url: str = "https://api.exchangeratesapi.io/v1"


class ExchangeratesapiIntegration(Integration):
    """Currency symbols and exchange rates (latest or historical)."""

    def __init__(self, configuration: ExchangeratesapiIntegrationConfiguration):
        super().__init__(configuration)
        self.configuration = configuration
        self._symbols: dict[str, Any] | None = None

    async def _get(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        response = await request(
            self.configuration,
            "GET",
            f"{self.configuration.base_url}{endpoint}",
            service=SERVICE,
            params={"access_key": self.configuration.api_key, **(params or {})},
        )
        return response.json() if response.content else {}

    async def list_symbols(self) -> dict[str, Any]:
        """All currency symbols and their names."""
        if self._symbols is None:
            self._symbols = await self._get("/symbols")
        return self._symbols

    async def get_exchange_rates(
        self, date: str = "latest", base: str = "EUR", symbols: list[str] | None = None
    ) -> dict[str, Any]:
        """Rates of ``base`` on ``date`` (YYYY-MM-DD or "latest"), for ``symbols`` or all."""
        params: dict[str, Any] = {"base": base}
        if symbols:
            params["symbols"] = ",".join(symbols)
        return await self._get(f"/{date}", params)


def as_tools(configuration: ExchangeratesapiIntegrationConfiguration) -> list[Any]:
    """LangChain tools over the integration."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = ExchangeratesapiIntegration(configuration)

    class GetExchangeRatesSchema(BaseModel):
        date: str = Field(
            "latest",
            description="The date to get the exchange rates for in format YYYY-MM-DD. Default is 'latest'.",
        )
        base: str = Field(
            "EUR",
            description="The base currency to get the exchange rates for. Default is 'EUR'.",
        )
        symbols: list[str] | None = Field(
            None,
            description="The symbols to get the exchange rates for. Default is all symbols.",
        )

    class ListSymbolsSchema(BaseModel):
        pass

    async def get_exchange_rates(
        date: str = "latest", base: str = "EUR", symbols: list[str] | None = None
    ) -> dict[str, Any]:
        return await integration.get_exchange_rates(date, base, symbols)

    async def list_symbols() -> dict[str, Any]:
        return await integration.list_symbols()

    return [
        StructuredTool(
            name="exchangeratesapi_get_exchange_rates",
            description="Get exchange rates for a given date, base and symbols.",
            coroutine=get_exchange_rates,
            args_schema=GetExchangeRatesSchema,
        ),
        StructuredTool(
            name="exchangeratesapi_list_symbols",
            description="List all currencies symbols and their names.",
            coroutine=list_symbols,
            args_schema=ListSymbolsSchema,
        ),
    ]
