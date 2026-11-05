"""SendGrid: a remote ABI module (email delivery).

Runs in its own process (``python -m naas_abi_apps.sendgrid``) and reaches the
engine only through NATS. Replaces the in-engine
``naas_abi_marketplace.applications.sendgrid``. Credentials are engine secrets
(``SENDGRID_API_KEY``), read once at start: restart
the module after setting them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from naas_abi_apps.common.agents import read_secrets
from naas_abi_apps.common.runtime import serve_until_stopped
from naas_abi_apps.sendgrid.agents.SendGridAgent import DESCRIPTION, NAME, create_agent
from naas_abi_sdk import (
    AgentDescriptor,
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)

MODULE_ID = "applications.sendgrid"
AGENT_INVOKE = ("agent.invoke.v1",)

logger = logging.getLogger(__name__)


@dataclass
class SendGridConfiguration(ModuleConfiguration):
    # Names of the engine secrets holding the credentials.
    api_key_secret: str = "SENDGRID_API_KEY"
    # Canonical id of a chat model the engine registers; empty: its default.
    chat_model: str = ""

    def secret_names(self) -> dict[str, str]:
        """Integration field -> engine secret name."""
        return {
            "api_key": self.api_key_secret,
        }


class ABIModule(BaseModule[SendGridConfiguration]):
    Configuration = SendGridConfiguration
    module_id = MODULE_ID
    package_version = "0.1.0"
    dependencies = ModuleDependencies(services=("model_registry", "document", "secret"))
    agents = (AgentDescriptor(NAME, DESCRIPTION, capabilities=AGENT_INVOKE),)

    async def on_initialized(self) -> None:
        credentials = await read_secrets(self.engine, self.configuration.secret_names())
        if not all(credentials.values()):
            missing = [
                s
                for f, s in self.configuration.secret_names().items()
                if not credentials[f]
            ]
            logger.warning(
                "%s: secrets %s not set; tools may be missing", MODULE_ID, missing
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
