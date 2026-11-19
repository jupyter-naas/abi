"""Nebari: a remote ABI module (open-source data science platform).

Runs in its own process (``python -m naas_abi_apps.nebari``) and reaches the
engine only through NATS. Replaces the in-engine
``naas_abi_marketplace.applications.nebari``. Its ``ontologies/*.ttl`` (the
Nebari ontology and its SPARQL query templates) are sent to the engine's schema
graph once the module is READY.
"""

from __future__ import annotations

from dataclasses import dataclass

from naas_abi_apps.common.runtime import serve_until_stopped
from naas_abi_apps.nebari.agents.NebariAgent import DESCRIPTION, NAME, create_agent
from naas_abi_sdk import (
    AgentDescriptor,
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)

MODULE_ID = "applications.nebari"
AGENT_INVOKE = ("agent.invoke.v1",)


@dataclass
class NebariConfiguration(ModuleConfiguration):
    # Canonical id of a chat model the engine registers; empty: its default.
    # (The in-engine module picked qwen3 in airgap mode, gpt-4.1 otherwise.)
    chat_model: str = ""


class ABIModule(BaseModule[NebariConfiguration]):
    Configuration = NebariConfiguration
    module_id = MODULE_ID
    package_version = "0.1.0"
    # triple_store: ontologies/ goes to the engine's schema graph.
    dependencies = ModuleDependencies(
        services=("model_registry", "document", "triple_store")
    )
    agents = (AgentDescriptor(NAME, DESCRIPTION, capabilities=AGENT_INVOKE),)

    async def on_initialized(self) -> None:
        agent = await create_agent(
            self.engine, MODULE_ID, chat_model=self.configuration.chat_model
        )
        self.expose_agent(NAME, agent.as_handler())

    async def run(self) -> None:
        await serve_until_stopped(self)
