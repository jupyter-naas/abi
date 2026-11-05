"""Agicap: a remote ABI module (cash-flow management).

Runs in its own process (``python -m naas_abi_apps.agicap``) and reaches the
engine only through NATS. Replaces the in-engine
``naas_abi_marketplace.applications.agicap``. Credentials are engine secrets
(``AGICAP_*``), read once at start.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from naas_abi_apps.agicap.agents.AgicapAgent import DESCRIPTION, NAME, create_agent
from naas_abi_apps.common.agents import read_secrets
from naas_abi_apps.common.runtime import serve_until_stopped
from naas_abi_sdk import (
    AgentDescriptor,
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)

MODULE_ID = "applications.agicap"
AGENT_INVOKE = ("agent.invoke.v1",)

logger = logging.getLogger(__name__)


@dataclass
class AgicapConfiguration(ModuleConfiguration):
    # Names of the engine secrets holding the credentials.
    username_secret: str = "AGICAP_USERNAME"
    password_secret: str = "AGICAP_PASSWORD"
    client_id_secret: str = "AGICAP_CLIENT_ID"
    client_secret_secret: str = "AGICAP_CLIENT_SECRET"
    bearer_token_secret: str = "AGICAP_BEARER_TOKEN"
    api_token_secret: str = "AGICAP_API_TOKEN"
    # Canonical id of a chat model the engine registers; empty: its default.
    chat_model: str = ""

    def secret_names(self) -> dict[str, str]:
        """Integration field -> engine secret name."""
        return {
            "username": self.username_secret,
            "password": self.password_secret,
            "client_id": self.client_id_secret,
            "client_secret": self.client_secret_secret,
            "bearer_token": self.bearer_token_secret,
            "api_token": self.api_token_secret,
        }


class ABIModule(BaseModule[AgicapConfiguration]):
    Configuration = AgicapConfiguration
    module_id = MODULE_ID
    package_version = "0.1.0"
    dependencies = ModuleDependencies(services=("model_registry", "document", "secret"))
    agents = (AgentDescriptor(NAME, DESCRIPTION, capabilities=AGENT_INVOKE),)

    async def on_initialized(self) -> None:
        credentials = await read_secrets(self.engine, self.configuration.secret_names())
        if not any(credentials.values()):
            logger.warning(
                "%s: no AGICAP_* secret set; the agent runs without tools", MODULE_ID
            )
        agent = await create_agent(
            self.engine,
            MODULE_ID,
            credentials=credentials,
            chat_model=self.configuration.chat_model,
        )
        self.expose_agent(NAME, agent.as_handler())

    async def run(self) -> None:
        await serve_until_stopped(self)
