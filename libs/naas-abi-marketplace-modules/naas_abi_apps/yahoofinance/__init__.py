"""Yahoo Finance: a remote ABI module (public market data).

Runs in its own process (``python -m naas_abi_apps.yahoofinance``) and reaches
the engine only through NATS. Replaces the in-engine
``naas_abi_marketplace.applications.yahoofinance``. No credentials.
"""

from __future__ import annotations

from dataclasses import dataclass

from naas_abi_apps.common.runtime import serve_until_stopped
from naas_abi_apps.yahoofinance.agents.YfinanceAgent import (
    DESCRIPTION,
    NAME,
    create_agent,
)
from naas_abi_sdk import (
    AgentDescriptor,
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)

MODULE_ID = "applications.yahoofinance"
AGENT_INVOKE = ("agent.invoke.v1",)


@dataclass
class YahooFinanceConfiguration(ModuleConfiguration):
    # Object storage prefix the results are archived under.
    datastore_path: str = "yahoofinance"
    # Canonical id of a chat model the engine registers; empty: its default.
    chat_model: str = ""


class ABIModule(BaseModule[YahooFinanceConfiguration]):
    Configuration = YahooFinanceConfiguration
    module_id = MODULE_ID
    package_version = "0.1.0"
    dependencies = ModuleDependencies(
        services=("model_registry", "document", "object_storage")
    )
    agents = (AgentDescriptor(NAME, DESCRIPTION, capabilities=AGENT_INVOKE),)

    async def on_initialized(self) -> None:
        agent = await create_agent(
            self.engine,
            MODULE_ID,
            datastore_path=self.configuration.datastore_path,
            chat_model=self.configuration.chat_model,
        )
        self.expose_agent(NAME, agent.as_handler())

    async def run(self) -> None:
        await serve_until_stopped(self)
