"""Sanax: a remote ABI module (LinkedIn Sales Navigator exports).

Runs in its own process (``python -m naas_abi_apps.sanax``) and reaches the
engine only through NATS. Replaces the in-engine
``naas_abi_marketplace.applications.sanax``. The agent queries people,
companies, positions and locations with the SPARQL templates of
``ontologies/`` (also sent to the schema graph); the Excel import is the
durable workflow ``pipeline.sanax_linked_in_sales_navigator_extractor_pipeline``.
"""

from __future__ import annotations

from dataclasses import dataclass

from naas_abi_apps.common.runtime import serve_until_stopped
from naas_abi_apps.sanax.agents.SanaxAgent import DESCRIPTION, NAME, create_agent
from naas_abi_sdk import (
    AgentDescriptor,
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)

MODULE_ID = "applications.sanax"
AGENT_INVOKE = ("agent.invoke.v1",)


@dataclass
class SanaxConfiguration(ModuleConfiguration):
    # Named graph the imported people go to (the in-engine default graph).
    graph_name: str = "http://ontology.naas.ai/graph/default"
    # Canonical id of a chat model the engine registers; empty: its default.
    chat_model: str = ""


class ABIModule(BaseModule[SanaxConfiguration]):
    Configuration = SanaxConfiguration
    module_id = MODULE_ID
    package_version = "0.1.0"
    dependencies = ModuleDependencies(
        services=("model_registry", "document", "triple_store", "object_storage")
    )
    agents = (AgentDescriptor(NAME, DESCRIPTION, capabilities=AGENT_INVOKE),)

    async def on_initialized(self) -> None:
        agent = await create_agent(
            self.engine, MODULE_ID, chat_model=self.configuration.chat_model
        )
        self.expose_agent(NAME, agent.as_handler())

    async def run(self) -> None:
        await serve_until_stopped(self)
