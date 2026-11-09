"""ArXiv: a remote ABI module (academic papers).

Runs in its own process (``python -m naas_abi_apps.arxiv``) and reaches the
engine only through NATS. Replaces the in-engine
``naas_abi_marketplace.applications.arxiv``. Papers the agent saves go to the
``graph_name`` graph of the engine's triple store, their PDFs to object
storage; ``ontologies/ArXivOntology.ttl`` goes to the schema graph. The
pipeline is also the durable workflow ``pipeline.ar_xiv_paper_pipeline``.
"""

from __future__ import annotations

from dataclasses import dataclass

from naas_abi_apps.arxiv.agents.ArXivAgent import (
    DESCRIPTION,
    NAME,
    build_tools,
    create_agent,
)
from naas_abi_apps.arxiv.integrations.ArXivIntegration import (
    ArXivIntegration,
    ArXivIntegrationConfiguration,
)
from naas_abi_apps.arxiv.queries import ArXivQueries
from naas_abi_apps.common.runtime import serve_until_stopped
from naas_abi_sdk import (
    AgentDescriptor,
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)

MODULE_ID = "applications.arxiv"
AGENT_INVOKE = ("agent.invoke.v1",)


@dataclass
class ArXivConfiguration(ModuleConfiguration):
    # Named graph the saved papers go to.
    graph_name: str = "http://ontology.naas.ai/graph/arxiv"
    # Object storage prefix of the PDFs.
    datastore_path: str = "arxiv"
    # Canonical id of a chat model the engine registers; empty: its default.
    chat_model: str = ""


class ABIModule(BaseModule[ArXivConfiguration]):
    Configuration = ArXivConfiguration
    module_id = MODULE_ID
    package_version = "0.1.0"
    dependencies = ModuleDependencies(
        services=("model_registry", "document", "triple_store", "object_storage")
    )
    agents = (AgentDescriptor(NAME, DESCRIPTION, capabilities=AGENT_INVOKE),)

    async def on_initialized(self) -> None:
        await self.build_processes()
        tools = build_tools(
            ArXivIntegration(ArXivIntegrationConfiguration()),
            self.get_pipeline_instance("ar_xiv_paper_pipeline"),
            ArXivQueries(
                self.engine.services.triple_store, self.configuration.graph_name
            ),
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
