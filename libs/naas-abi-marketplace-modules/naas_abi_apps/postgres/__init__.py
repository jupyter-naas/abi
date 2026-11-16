"""PostgreSQL: a remote ABI module (query a PostgreSQL database).

Runs in its own process (``python -m naas_abi_apps.postgres``) and reaches the
engine only through NATS. Replaces the in-engine
``naas_abi_marketplace.applications.postgres``. Credentials are engine secrets
(``POSTGRES_AGENT_HOST``, ``POSTGRES_AGENT_PORT``, ``POSTGRES_AGENT_DBNAME``,
``POSTGRES_AGENT_USER``, ``POSTGRES_AGENT_PASSWORD``), read once at start:
restart the module after setting them. ``POSTGRES_*_SECRET`` names others.

The in-engine module read ``POSTGRES_HOST`` and the like, which are the
engine's own database variables in many projects: by default its agent could
read, and write, the engine's database. The defaults are now names of their
own, and queries are read-only unless ``POSTGRES_READ_ONLY=false``
(``PostgresIntegration``). Give the module a role with only the rights it
needs as well.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from naas_abi_apps.common.agents import read_secrets
from naas_abi_apps.common.runtime import serve_until_stopped
from naas_abi_apps.postgres.agents.PostgresAgent import DESCRIPTION, NAME, create_agent
from naas_abi_sdk import (
    AgentDescriptor,
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)

MODULE_ID = "applications.postgres"
AGENT_INVOKE = ("agent.invoke.v1",)

logger = logging.getLogger(__name__)


@dataclass
class PostgresConfiguration(ModuleConfiguration):
    # Names of the engine secrets holding the credentials.
    host_secret: str = "POSTGRES_AGENT_HOST"
    port_secret: str = "POSTGRES_AGENT_PORT"
    database_secret: str = "POSTGRES_AGENT_DBNAME"
    user_secret: str = "POSTGRES_AGENT_USER"
    password_secret: str = "POSTGRES_AGENT_PASSWORD"
    # Canonical id of a chat model the engine registers; empty: its default.
    chat_model: str = ""
    # One read-only statement per query; false lets the agent write.
    read_only: bool = True

    def secret_names(self) -> dict[str, str]:
        """Integration field -> engine secret name."""
        return {
            "host": self.host_secret,
            "port": self.port_secret,
            "database": self.database_secret,
            "user": self.user_secret,
            "password": self.password_secret,
        }


class ABIModule(BaseModule[PostgresConfiguration]):
    Configuration = PostgresConfiguration
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
            read_only=self.configuration.read_only,
        )
        self.expose_agent(NAME, agent.as_handler())

    async def run(self) -> None:
        await serve_until_stopped(self)
