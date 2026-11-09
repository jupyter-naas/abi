"""Pennylane: a remote ABI module (French accounting platform).

Runs in its own process (``python -m naas_abi_apps.pennylane``) and reaches the
engine only through NATS, with ``naas-abi-sdk``. It never imports
``naas_abi_core``. Replaces the in-engine
``naas_abi_marketplace.applications.pennylane``.

The API token is the engine secret named by ``api_key_secret``
(``PENNYLANE_API_KEY``), read once at start: restart the module after setting it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from naas_abi_apps.common.runtime import serve_until_stopped
from naas_abi_apps.pennylane.agents.PennylaneAgent import (
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

# Stable across replicas and restarts: discovery and agent memory are keyed by it.
MODULE_ID = "applications.pennylane"
AGENT_INVOKE = ("agent.invoke.v1",)

logger = logging.getLogger(__name__)


@dataclass
class PennylaneConfiguration(ModuleConfiguration):
    # Name of the engine secret holding the Pennylane API token.
    api_key_secret: str = "PENNYLANE_API_KEY"
    # Object storage prefix the API results are archived under.
    datastore_path: str = "pennylane"
    # Canonical id of a chat model the engine registers; empty: its default.
    chat_model: str = ""


class ABIModule(BaseModule[PennylaneConfiguration]):
    Configuration = PennylaneConfiguration
    module_id = MODULE_ID
    package_version = "0.1.0"
    dependencies = ModuleDependencies(
        services=("model_registry", "document", "secret", "object_storage")
    )
    agents = (AgentDescriptor(NAME, DESCRIPTION, capabilities=AGENT_INVOKE),)

    async def on_initialized(self) -> None:
        api_key = await self.engine.services.secret.get(
            self.configuration.api_key_secret, None
        )
        if not api_key:
            logger.warning(
                "%s: secret %s is not set; the agent runs without Pennylane tools",
                MODULE_ID,
                self.configuration.api_key_secret,
            )
        agent = await create_agent(
            self.engine,
            MODULE_ID,
            api_key=api_key,
            datastore_path=self.configuration.datastore_path,
            chat_model=self.configuration.chat_model,
        )
        self.expose_agent(NAME, agent.as_handler())

    async def run(self) -> None:
        await serve_until_stopped(self)
