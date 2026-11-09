"""PubMed: a remote ABI module (biomedical literature).

Runs in its own process (``python -m naas_abi_apps.pubmed``) and reaches the
engine only through NATS. Replaces the in-engine
``naas_abi_marketplace.applications.pubmed`` (its Dagster orchestration was
empty, so there is no job). The search is also the durable workflow
``pipeline.pub_med_pipeline``; ``ontologies/PubMed.ttl`` goes to the schema
graph.
"""

from __future__ import annotations

from dataclasses import dataclass

from naas_abi_apps.common.runtime import serve_until_stopped
from naas_abi_apps.pubmed.agents.PubMedAgent import (
    DESCRIPTION,
    NAME,
    build_tools,
    create_agent,
)
from naas_abi_sdk import (
    AgentDescriptor,
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)

MODULE_ID = "applications.pubmed"
AGENT_INVOKE = ("agent.invoke.v1",)


@dataclass
class PubMedConfiguration(ModuleConfiguration):
    # Object storage prefix of the module's files (PDFs under <path>/pdfs).
    datastore_path: str = "pubmed"
    # Canonical id of a chat model the engine registers; empty: its default.
    chat_model: str = ""


class ABIModule(BaseModule[PubMedConfiguration]):
    Configuration = PubMedConfiguration
    module_id = MODULE_ID
    package_version = "0.1.0"
    dependencies = ModuleDependencies(
        services=("model_registry", "document", "object_storage", "triple_store")
    )
    agents = (AgentDescriptor(NAME, DESCRIPTION, capabilities=AGENT_INVOKE),)

    async def on_initialized(self) -> None:
        await self.build_processes()
        tools = build_tools(
            self.get_pipeline_instance("pub_med_pipeline"),
            self.engine.services.object_storage,
            f"{self.configuration.datastore_path}/pdfs",
        )
        agent = await create_agent(
            self.engine,
            MODULE_ID,
            tools=tools,
            chat_model=self.configuration.chat_model,
        )
        self.expose_agent(NAME, agent.as_handler())

    async def run(self) -> None:
        await serve_until_stopped(self)
