"""Agicap (cash-flow management) API, async, on ``naas_abi_sdk`` only.

Port of ``naas_abi_marketplace.applications.agicap.integrations``: same
endpoints and tool names. The bearer token of the app API is fetched with the
username and password on first use when none is configured.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from naas_abi_apps.common.http import HttpConfiguration, request_json
from naas_abi_sdk.integration import Integration

SERVICE = "Agicap"
APP_URL = "https://app.agicap.com/api"
OPENAPI_URL = "https://openapi.agicap.com/api"
DEBTS_URL = "https://debt-management.agicap.com/v3"
PAGE_SIZE = 100


@dataclass
class AgicapIntegrationConfiguration(HttpConfiguration):
    """api_token: public API (companies). bearer_token, or username + password
    (+ client_secret): app API (accounts, transactions, balances, debts)."""

    username: str = ""
    password: str = ""
    api_token: str = ""
    bearer_token: str = ""
    client_id: str = ""
    client_secret: str = ""
    base_url: str = APP_URL


def flatten(d: dict[str, Any], parent_key: str = "", sep: str = "_") -> dict[str, Any]:
    """``{"a": {"b": 1}}`` -> ``{"a_b": 1}``."""
    items: dict[str, Any] = {}
    for key, value in d.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        if isinstance(value, dict):
            items.update(flatten(value, new_key, sep=sep))
        else:
            items[new_key] = value
    return items


class AgicapIntegration(Integration):
    """Agicap API client: companies, accounts, transactions, balances, debts."""

    def __init__(self, configuration: AgicapIntegrationConfiguration):
        super().__init__(configuration)
        self.configuration = configuration
        self._bearer_token = configuration.bearer_token

    async def _bearer(self) -> str:
        if not self._bearer_token:
            token = await request_json(
                self.configuration,
                "POST",
                f"{self.configuration.base_url}/public/auth/v1/token",
                service=SERVICE,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "password",
                    "client_id": "legacy-token",
                    "client_secret": self.configuration.client_secret,
                    "scope": "agicap:app",
                    "username": self.configuration.username,
                    "password": self.configuration.password,
                },
            )
            self._bearer_token = token.get("access_token") or ""
        return self._bearer_token

    async def _app_headers(self, company_id: str | None = None) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "fr",
            "Authorization": f"Bearer {await self._bearer()}",
            "Content-Type": "application/json",
        }
        if company_id is not None:
            headers["EntrepriseId"] = company_id
        return headers

    async def list_companies(self) -> Any:
        """Companies accessible with the public API token."""
        return await request_json(
            self.configuration,
            "GET",
            f"{OPENAPI_URL}/companies",
            service=SERVICE,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.configuration.api_token}",
            },
        )

    async def get_company_accounts(self, company_id: str) -> Any:
        """Bank accounts of a company."""
        result = await request_json(
            self.configuration,
            "GET",
            f"{APP_URL}/banque/GetAll",
            service=SERVICE,
            headers=await self._app_headers(company_id),
        )
        return result.get("Result")

    async def get_transactions(
        self, company_id: str, account_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Paid transactions of an account, newest first, flattened, at most ``limit``."""
        take = min(PAGE_SIZE, limit)
        skip = 0
        data: list[dict[str, Any]] = []
        headers = await self._app_headers(company_id)
        while True:
            payload = {
                "filters": {
                    "nature": 1,
                    "statusesToInclude": 0,
                    "statusesToExclude": 0,
                    "transactionWithProjectsDistributionStale": False,
                    "includeTransactionWithoutProject": False,
                    "transactionsType": 0,
                    "categorizationState": 0,
                    "bankAccountIds": [str(account_id)],
                },
                "sort": {"asc": False, "sortField": "0"},
                "pagination": {"skip": skip, "take": take},
            }
            page = await request_json(
                self.configuration,
                "POST",
                f"{self.configuration.base_url}/paidtransaction/GetByFilters",
                service=SERVICE,
                headers=headers,
                json=payload,
            )
            result = page.get("Result") or []
            data.extend(flatten(r) for r in result)
            if not result or len(data) >= limit:
                return data[:limit]
            skip += take

    async def get_balance(self, company_id: str, account_id: str | None = None) -> Any:
        """Cash balances of an account, or consolidated without ``account_id``."""
        path = (
            f"bank/{account_id}/cash-balances" if account_id else "bank/cash-balances"
        )
        return await request_json(
            self.configuration,
            "GET",
            f"{APP_URL}/forecasting/v2/{path}",
            service=SERVICE,
            headers=await self._app_headers(company_id),
            params={"frequency": 2},
        )

    async def get_debts(self, company_id: str) -> Any:
        """Debts of a company."""
        return await request_json(
            self.configuration,
            "GET",
            f"{DEBTS_URL}/entities/{company_id}/debts",
            service=SERVICE,
            headers=await self._app_headers(),
        )


def as_tools(configuration: AgicapIntegrationConfiguration) -> list[Any]:
    """LangChain tools over the integration."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = AgicapIntegration(configuration)

    class ListCompaniesSchema(BaseModel):
        pass

    class CompanySchema(BaseModel):
        company_id: str = Field(..., description="The ID of the company")

    class GetTransactionsSchema(BaseModel):
        company_id: str = Field(..., description="The ID of the company")
        account_id: str = Field(..., description="The ID of the account")
        limit: int = Field(10, description="The number of transactions to retrieve")

    class GetBalanceSchema(BaseModel):
        company_id: str = Field(..., description="The ID of the company")
        account_id: str | None = Field(None, description="The ID of the account")

    async def list_companies() -> Any:
        return await integration.list_companies()

    async def get_company_accounts(company_id: str) -> Any:
        return await integration.get_company_accounts(company_id)

    async def get_transactions(
        company_id: str, account_id: str, limit: int = 10
    ) -> Any:
        return await integration.get_transactions(company_id, account_id, limit)

    async def get_balance(company_id: str, account_id: str | None = None) -> Any:
        return await integration.get_balance(company_id, account_id)

    async def get_debts(company_id: str) -> Any:
        return await integration.get_debts(company_id)

    return [
        StructuredTool(
            name="agicap_list_companies",
            description="Get list of accessible companies with their ID from Agicap.",
            coroutine=list_companies,
            args_schema=ListCompaniesSchema,
        ),
        StructuredTool(
            name="agicap_get_company_accounts",
            description="Get all accounts with their ID for a company in Agicap.",
            coroutine=get_company_accounts,
            args_schema=CompanySchema,
        ),
        StructuredTool(
            name="agicap_get_transactions",
            description="Get all transactions for a specific account in Agicap.",
            coroutine=get_transactions,
            args_schema=GetTransactionsSchema,
        ),
        StructuredTool(
            name="agicap_get_balance",
            description="Get account balance information from Agicap. If account ID is not provided, a consolidated balance will be returned.",
            coroutine=get_balance,
            args_schema=GetBalanceSchema,
        ),
        StructuredTool(
            name="agicap_get_debts",
            description="Get company debts information from Agicap.",
            coroutine=get_debts,
            args_schema=CompanySchema,
        ),
    ]
