"""PostgreSQL: a remote ABI module (query a PostgreSQL database).

Runs in its own process (``python -m naas_abi_apps.postgres``) and reaches the
engine only through NATS. Replaces the in-engine
``naas_abi_marketplace.applications.postgres``. Credentials are engine secrets
(``POSTGRES_HOST``, ``POSTGRES_PORT``, ``POSTGRES_DBNAME``, ``POSTGRES_USER``, ``POSTGRES_PASSWORD``), read once at start: restart
the module after setting them.

The default secret names are the in-engine module's, which are also the
engine's own database variables in many projects: point ``POSTGRES_*_SECRET``
at other secrets to query another database.
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
    host_secret: str = "POSTGRES_HOST"
    port_secret: str = "POSTGRES_PORT"
    database_secret: str = "POSTGRES_DBNAME"
    user_secret: str = "POSTGRES_USER"
    password_secret: str = "POSTGRES_PASSWORD"
    # Canonical id of a chat model the engine registers; empty: its default.
    chat_model: str = ""

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
        )
        self.expose_agent(NAME, agent.as_handler())

    async def run(self) -> None:
        await serve_until_stopped(self)
