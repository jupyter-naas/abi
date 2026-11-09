"""PowerPoint: a remote ABI module (presentations from a template).

Runs in its own process (``python -m naas_abi_apps.powerpoint``) and reaches
the engine only through NATS. Replaces the in-engine
``naas_abi_marketplace.applications.powerpoint``.

The template is ``template_path``: an object storage path (prefix/key), or by
default the bundled ``templates/TemplateMinimal.pptx`` (``make_template``).
Decks are saved under ``datastore_path``; with the ``NAAS_API_KEY``,
``WORKSPACE_ID`` and ``STORAGE_NAME`` secrets they are also uploaded to the Naas
workspace storage for a public download URL. Presentations, slides and shapes
go to ``graph_name``; ``ontologies/`` goes to the schema graph.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from naas_abi_apps.common.agents import read_secrets
from naas_abi_apps.common.runtime import serve_until_stopped
from naas_abi_apps.naas.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
)
from naas_abi_apps.powerpoint.agents.PowerPointAgent import (
    DESCRIPTION,
    NAME,
    build_tools,
    create_agent,
)
from naas_abi_apps.powerpoint.pipelines.AddPowerPointPresentationPipeline import (
    BUNDLED_TEMPLATE,
    AddPowerPointPresentationPipeline,
    read_presentation_bytes,
)
from naas_abi_apps.powerpoint.workflows.CreatePresentationFromTemplateWorkflow import (
    CreatePresentationFromTemplateWorkflow,
    CreatePresentationFromTemplateWorkflowConfiguration,
)
from naas_abi_sdk import (
    AgentDescriptor,
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)

MODULE_ID = "applications.powerpoint"
AGENT_INVOKE = ("agent.invoke.v1",)
PIPELINE = "add_power_point_presentation_pipeline"
WORKFLOW = "create_presentation_from_template_workflow"

logger = logging.getLogger(__name__)


@dataclass
class PowerPointConfiguration(ModuleConfiguration):
    # Template: object storage prefix/key, or the bundled minimal template.
    template_path: str = BUNDLED_TEMPLATE
    # Object storage prefix the created decks are saved under.
    datastore_path: str = "powerpoint/presentations"
    # Named graph the presentations go to (the in-engine default graph).
    graph_name: str = "http://ontology.naas.ai/graph/default"
    # Engine secrets for the Naas upload (all three, or no upload).
    naas_api_key_secret: str = "NAAS_API_KEY"
    workspace_id_secret: str = "WORKSPACE_ID"
    storage_name_secret: str = "STORAGE_NAME"
    # Canonical id of a chat model the engine registers; empty: its default.
    chat_model: str = ""


class ABIModule(BaseModule[PowerPointConfiguration]):
    Configuration = PowerPointConfiguration
    module_id = MODULE_ID
    package_version = "0.1.0"
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

    async def _naas(self) -> tuple[NaasIntegration | None, str | None, str | None]:
        c = self.configuration
        secrets = await read_secrets(
            self.engine,
            {
                "api_key": c.naas_api_key_secret,
                "workspace_id": c.workspace_id_secret,
                "storage_name": c.storage_name_secret,
            },
        )
        if not all(secrets.values()):
            logger.warning(
                "%s: Naas secrets not all set; decks are stored without a download URL",
                MODULE_ID,
            )
            return None, None, None
        naas = NaasIntegration(NaasIntegrationConfiguration(**secrets))
        return naas, secrets["workspace_id"], secrets["storage_name"]

    async def on_initialized(self) -> None:
        services = self.engine.services
        pipeline = AddPowerPointPresentationPipeline.New(self)
        naas, workspace_id, storage_name = await self._naas()
        workflow = CreatePresentationFromTemplateWorkflow(
            CreatePresentationFromTemplateWorkflowConfiguration(
                storage=services.object_storage,
                pipeline=pipeline,
                template_path=self.configuration.template_path,
                datastore_path=self.configuration.datastore_path,
                naas=naas,
                workspace_id=workspace_id,
                storage_name=storage_name,
            )
        )
        self.expose_pipeline(PIPELINE, pipeline)
        self.expose_workflow(WORKFLOW, workflow)
        await self.build_processes()
        template = await read_presentation_bytes(
            services.object_storage, self.configuration.template_path
        )
        tools = build_tools(template, workflow, pipeline, services.triple_store)
        agent = await create_agent(
            self.engine,
            MODULE_ID,
            tools=tools,
            chat_model=self.configuration.chat_model,
        )
        self.expose_agent(NAME, agent.as_handler())

    async def run(self) -> None:
        await serve_until_stopped(self)
