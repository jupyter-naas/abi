"""Google Search: a remote ABI module (Programmable Search Engine).

Runs in its own process (``python -m naas_abi_apps.google_search``) and reaches
the engine only through NATS. Replaces the in-engine
``naas_abi_marketplace.applications.google_search`` (still loaded in-process by
the in-engine ``linkedin`` module until that one is ported). Credentials are
engine secrets (``GOOGLE_CUSTOM_SEARCH_API_KEY``,
``GOOGLE_CUSTOM_SEARCH_ENGINE_ID``), read at start. The LinkedIn page searches
are also durable workflows other modules start by name,
``workflow.search_linked_in_profile_page_workflow`` and
``workflow.search_linked_in_organization_page_workflow``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from naas_abi_apps.common.agents import read_secrets
from naas_abi_apps.common.runtime import serve_until_stopped
from naas_abi_apps.google_search.agents.GoogleSearchAgent import (
    DESCRIPTION,
    NAME,
    create_agent,
    workflow_tools,
)
from naas_abi_apps.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
    GoogleProgrammableSearchEngineIntegrationConfiguration,
)
from naas_abi_sdk import (
    AgentDescriptor,
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)

MODULE_ID = "applications.google_search"
AGENT_INVOKE = ("agent.invoke.v1",)

logger = logging.getLogger(__name__)


@dataclass
class GoogleSearchConfiguration(ModuleConfiguration):
    # Names of the engine secrets holding the credentials.
    api_key_secret: str = "GOOGLE_CUSTOM_SEARCH_API_KEY"
    search_engine_id_secret: str = "GOOGLE_CUSTOM_SEARCH_ENGINE_ID"
    # Object storage prefix the results are archived under.
    datastore_path: str = "google_search"
    # Canonical id of a chat model the engine registers; empty: its default.
    chat_model: str = ""

    def secret_names(self) -> dict[str, str]:
        return {
            "api_key": self.api_key_secret,
            "search_engine_id": self.search_engine_id_secret,
        }


class ABIModule(BaseModule[GoogleSearchConfiguration]):
    Configuration = GoogleSearchConfiguration
    module_id = MODULE_ID
    package_version = "0.1.0"
    # triple_store: ontologies/ goes to the engine's schema graph.
    dependencies = ModuleDependencies(
        services=(
            "model_registry",
            "document",
            "secret",
            "object_storage",
            "triple_store",
        )
    )
    agents = (AgentDescriptor(NAME, DESCRIPTION, capabilities=AGENT_INVOKE),)

    def integration_configuration(
        self, credentials: dict[str, str]
    ) -> GoogleProgrammableSearchEngineIntegrationConfiguration:
        return GoogleProgrammableSearchEngineIntegrationConfiguration(
            api_key=credentials["api_key"],
            search_engine_id=credentials["search_engine_id"],
            datastore_path=self.configuration.datastore_path,
            storage=self.engine.services.object_storage,
        )

    async def on_initialized(self) -> None:
        credentials = await read_secrets(self.engine, self.configuration.secret_names())
        integration = None
        extra_tools: list = []
        await self.build_processes()
        if all(credentials.values()):
            integration = self.integration_configuration(credentials)
            extra_tools = workflow_tools(
                self.get_workflow_instance("search_linked_in_profile_page_workflow"),
                self.get_workflow_instance(
                    "search_linked_in_organization_page_workflow"
                ),
            )
        else:
            logger.warning(
                "%s: search secrets not set; the agent runs without search tools",
                MODULE_ID,
            )
        agent = await create_agent(
            self.engine,
            MODULE_ID,
            integration=integration,
            extra_tools=extra_tools,
            chat_model=self.configuration.chat_model,
        )
        self.expose_agent(NAME, agent.as_handler())

    async def run(self) -> None:
        await serve_until_stopped(self)
