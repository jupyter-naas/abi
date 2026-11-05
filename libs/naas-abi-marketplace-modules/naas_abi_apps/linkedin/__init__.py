"""LinkedIn: a remote ABI module (LinkedIn through a member's session, and the
LinkedIn connections of the knowledge graph).

Runs in its own process (``python -m naas_abi_apps.linkedin``) and reaches the
engine only through NATS. Replaces the in-engine
``naas_abi_marketplace.applications.linkedin``. Two agents:

- ``LinkedIn``: the LinkedIn API with the member's cookies (engine secrets
  ``li_at``, ``JSESSIONID``, and ``LINKEDIN_PROFILE_URL``), the Google searches
  for LinkedIn pages (``GOOGLE_CUSTOM_SEARCH_API_KEY``,
  ``GOOGLE_CUSTOM_SEARCH_ENGINE_ID``, with the ``google_search`` module's code),
  and the connection queries. Missing secrets: those tools are left out.
- ``LinkedIn_KG``: the connection queries and a name search over embeddings.

The connections themselves are written by the people module
(``ActOfConnectionsOnLinkedInExportPipeline``, from a LinkedIn
``Connections.csv``), which also owns the LinkedIn ontology. The embeddings of
the people and organizations are brought up to date once at start and by
``workflow.create_class_embeddings_workflow``. Secrets are read once at start:
restart the module after setting them.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from naas_abi_apps.common.agents import read_secrets
from naas_abi_apps.common.runtime import serve_until_stopped
from naas_abi_apps.common.sparql_templates import module_queries, query_tools
from naas_abi_apps.linkedin.agents import LinkedInAgent, LinkedInKGAgent
from naas_abi_apps.linkedin.integrations.LinkedInIntegration import (
    LinkedInIntegrationConfiguration,
    as_tools,
)
from naas_abi_apps.linkedin.workflows.CreateClassEmbeddingsWorkflow import (
    CreateClassEmbeddingsWorkflow,
    CreateClassEmbeddingsWorkflowConfiguration,
    CreateClassEmbeddingsWorkflowParameters,
    search_tools,
)
from naas_abi_sdk import (
    AgentDescriptor,
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)

MODULE_ID = "applications.linkedin"
AGENT_INVOKE = ("agent.invoke.v1",)
EMBEDDINGS_WORKFLOW = "create_class_embeddings_workflow"

logger = logging.getLogger(__name__)


@dataclass
class LinkedInConfiguration(ModuleConfiguration):
    # Names of the engine secrets: the member's session cookies and profile.
    li_at_secret: str = "li_at"
    jsessionid_secret: str = "JSESSIONID"
    profile_url_secret: str = "LINKEDIN_PROFILE_URL"
    # Google Programmable Search Engine, for the LinkedIn page searches.
    google_api_key_secret: str = "GOOGLE_CUSTOM_SEARCH_API_KEY"
    google_search_engine_id_secret: str = "GOOGLE_CUSTOM_SEARCH_ENGINE_ID"
    # Object storage prefix the API responses are archived under.
    datastore_path: str = "linkedin"
    # Canonical ids of models the engine registers; empty: its defaults.
    chat_model: str = ""
    embedding_model: str = ""
    # Bring the name embeddings up to date when the module starts.
    embed_at_start: bool = True


class ABIModule(BaseModule[LinkedInConfiguration]):
    Configuration = LinkedInConfiguration
    module_id = MODULE_ID
    package_version = "0.1.0"
    # triple_store: the connection queries; vector_store: the name search;
    # cache: a day of LinkedIn responses, as in-engine.
    dependencies = ModuleDependencies(
        services=(
            "model_registry",
            "document",
            "secret",
            "object_storage",
            "triple_store",
            "vector_store",
            "cache",
        )
    )
    agents = (
        AgentDescriptor(
            LinkedInAgent.NAME, LinkedInAgent.DESCRIPTION, capabilities=AGENT_INVOKE
        ),
        AgentDescriptor(
            LinkedInKGAgent.NAME, LinkedInKGAgent.DESCRIPTION, capabilities=AGENT_INVOKE
        ),
    )

    _embedding_task: asyncio.Task | None = None

    async def _linkedin_tools(self, secrets: dict[str, str]) -> list[Any]:
        if not (secrets["li_at"] and secrets["JSESSIONID"] and secrets["profile_url"]):
            logger.warning(
                "%s: LinkedIn secrets not all set (%s, %s, %s); no LinkedIn API tools",
                MODULE_ID,
                self.configuration.li_at_secret,
                self.configuration.jsessionid_secret,
                self.configuration.profile_url_secret,
            )
            return []
        services = self.engine.services
        return as_tools(
            LinkedInIntegrationConfiguration(
                li_at=secrets["li_at"],
                JSESSIONID=secrets["JSESSIONID"],
                linkedin_url=secrets["profile_url"],
                datastore_path=self.configuration.datastore_path,
                storage=services.object_storage,
                cache=services.cache,
            )
        )

    def _google_tools(self, secrets: dict[str, str]) -> list[Any]:
        if not (secrets["google_api_key"] and secrets["google_search_engine_id"]):
            logger.warning(
                "%s: Google search secrets not set; no page search", MODULE_ID
            )
            return []
        from naas_abi_apps.google_search.agents.GoogleSearchAgent import workflow_tools
        from naas_abi_apps.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
            GoogleProgrammableSearchEngineIntegrationConfiguration,
        )
        from naas_abi_apps.google_search.workflows.SearchLinkedInOrganizationPageWorkflow import (
            SearchLinkedInOrganizationPageWorkflow,
            SearchLinkedInOrganizationPageWorkflowConfiguration,
        )
        from naas_abi_apps.google_search.workflows.SearchLinkedInProfilePageWorkflow import (
            SearchLinkedInProfilePageWorkflow,
            SearchLinkedInProfilePageWorkflowConfiguration,
        )

        google = GoogleProgrammableSearchEngineIntegrationConfiguration(
            api_key=secrets["google_api_key"],
            search_engine_id=secrets["google_search_engine_id"],
            datastore_path="google_search",
            storage=self.engine.services.object_storage,
        )
        return workflow_tools(
            SearchLinkedInProfilePageWorkflow(
                SearchLinkedInProfilePageWorkflowConfiguration(integration=google)
            ),
            SearchLinkedInOrganizationPageWorkflow(
                SearchLinkedInOrganizationPageWorkflowConfiguration(integration=google)
            ),
        )

    async def on_initialized(self) -> None:
        c = self.configuration
        services = self.engine.services
        secrets = await read_secrets(
            self.engine,
            {
                "li_at": c.li_at_secret,
                "JSESSIONID": c.jsessionid_secret,
                "profile_url": c.profile_url_secret,
                "google_api_key": c.google_api_key_secret,
                "google_search_engine_id": c.google_search_engine_id_secret,
            },
        )
        registry = services.model_registry
        embeddings = (
            await registry.get_embedding_model(c.embedding_model)
            if c.embedding_model
            else await registry.get_default_embedding_model()
        ).model
        self.expose_workflow(
            EMBEDDINGS_WORKFLOW,
            CreateClassEmbeddingsWorkflow(
                CreateClassEmbeddingsWorkflowConfiguration(
                    triple_store=services.triple_store,
                    vector_store=services.vector_store,
                    embeddings=embeddings,
                )
            ),
        )
        await self.build_processes()

        queries = query_tools(
            module_queries(Path(__file__).parent), services.triple_store
        )
        agent_queries = [q for q in queries if q.name in LinkedInAgent.QUERIES]
        agent = await LinkedInAgent.create_agent(
            self.engine,
            MODULE_ID,
            tools=await self._linkedin_tools(secrets)
            + self._google_tools(secrets)
            + agent_queries,
            profile_url=secrets["profile_url"],
            chat_model=c.chat_model,
        )
        kg_agent = await LinkedInKGAgent.create_agent(
            self.engine,
            MODULE_ID,
            tools=search_tools(services.vector_store, embeddings) + queries,
            chat_model=c.chat_model,
        )
        self.expose_agent(LinkedInAgent.NAME, agent.as_handler())
        self.expose_agent(LinkedInKGAgent.NAME, kg_agent.as_handler())

    async def update_embeddings(self) -> None:
        """One pass of the embeddings workflow, in process; a failure is logged."""
        try:
            results = await self.get_workflow_instance(EMBEDDINGS_WORKFLOW).run(
                CreateClassEmbeddingsWorkflowParameters()
            )
            logger.info("%s: embeddings %s", MODULE_ID, results)
        except Exception:
            logger.exception("%s: embeddings update failed", MODULE_ID)

    async def run(self) -> None:
        if self.configuration.embed_at_start:
            self._embedding_task = asyncio.create_task(self.update_embeddings())
        try:
            await serve_until_stopped(self)
        finally:
            if self._embedding_task is not None:
                self._embedding_task.cancel()
