"""Naas: a remote ABI module (the Naas platform API).

Runs in its own process (``python -m naas_abi_apps.naas``) and reaches the
engine only through NATS. Replaces the agent and integration of the in-engine
``naas_abi_marketplace.applications.naas``. Credentials are engine secrets
(``NAAS_API_KEY``, ``WORKSPACE_ID``, ``STORAGE_NAME``), read at start.

Not ported (no caller outside in-engine modules): the ontology YAML workflows,
which build on core's ``OntologyYaml`` and are used in-process by the in-engine
``ontology_engineer``; the graph-to-Excel export; the image-to-asset pipeline;
``triggers.py``, which core no longer loads. See jupyter-naas/abi#1423.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from naas_abi_apps.common.agents import read_secrets
from naas_abi_apps.common.runtime import serve_until_stopped
from naas_abi_apps.naas.agents.NaasAgent import (
    DESCRIPTION,
    NAME,
    create_agent,
    tools_for,
)
from naas_abi_sdk import (
    AgentDescriptor,
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)

MODULE_ID = "applications.naas"
AGENT_INVOKE = ("agent.invoke.v1",)

logger = logging.getLogger(__name__)


@dataclass
class NaasConfiguration(ModuleConfiguration):
    # Names of the engine secrets.
    api_key_secret: str = "NAAS_API_KEY"
    workspace_id_secret: str = "WORKSPACE_ID"
    storage_name_secret: str = "STORAGE_NAME"
    # Canonical id of a chat model the engine registers; empty: its default.
    chat_model: str = ""

    def secret_names(self) -> dict[str, str]:
        return {
            "api_key": self.api_key_secret,
            "workspace_id": self.workspace_id_secret,
            "storage_name": self.storage_name_secret,
        }


class ABIModule(BaseModule[NaasConfiguration]):
    Configuration = NaasConfiguration
    module_id = MODULE_ID
    package_version = "0.1.0"
    dependencies = ModuleDependencies(
        services=("model_registry", "document", "secret", "triple_store")
    )
    agents = (AgentDescriptor(NAME, DESCRIPTION, capabilities=AGENT_INVOKE),)

    async def on_initialized(self) -> None:
        secrets = await read_secrets(self.engine, self.configuration.secret_names())
        if not secrets["api_key"]:
            logger.warning(
                "%s: secret %s not set; no Naas tools",
                MODULE_ID,
                self.configuration.api_key_secret,
            )
        agent = await create_agent(
            self.engine,
            MODULE_ID,
            tools=tools_for(**secrets),
            chat_model=self.configuration.chat_model,
        )
        self.expose_agent(NAME, agent.as_handler())

    async def run(self) -> None:
        await serve_until_stopped(self)
