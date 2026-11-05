"""GitHub: a remote ABI module (REST and GraphQL APIs).

Runs in its own process (``python -m naas_abi_apps.github``) and reaches the
engine only through NATS. Replaces the in-engine
``naas_abi_marketplace.applications.github`` (still imported in-process by the
in-engine ``support`` module, see jupyter-naas/abi#1423). The token is the
``GITHUB_ACCESS_TOKEN`` engine secret, read at start. ``ontologies/`` goes to
the engine's schema graph.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from naas_abi_apps.common.runtime import serve_until_stopped
from naas_abi_apps.github.agents.GitHubAgent import DESCRIPTION, NAME, create_agent
from naas_abi_sdk import (
    AgentDescriptor,
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)

MODULE_ID = "applications.github"
AGENT_INVOKE = ("agent.invoke.v1",)

logger = logging.getLogger(__name__)


@dataclass
class GitHubConfiguration(ModuleConfiguration):
    # Name of the engine secret holding the personal access token.
    access_token_secret: str = "GITHUB_ACCESS_TOKEN"
    # Canonical id of a chat model the engine registers; empty: its default.
    chat_model: str = ""


class ABIModule(BaseModule[GitHubConfiguration]):
    Configuration = GitHubConfiguration
    module_id = MODULE_ID
    package_version = "0.1.0"
    dependencies = ModuleDependencies(
        services=("model_registry", "document", "secret", "triple_store")
    )
    agents = (AgentDescriptor(NAME, DESCRIPTION, capabilities=AGENT_INVOKE),)

    async def on_initialized(self) -> None:
        token = await self.engine.services.secret.get(
            self.configuration.access_token_secret, None
        )
        if not token:
            logger.warning(
                "%s: secret %s not set; no GitHub tools",
                MODULE_ID,
                self.configuration.access_token_secret,
            )
        agent = await create_agent(
            self.engine,
            MODULE_ID,
            access_token=token,
            chat_model=self.configuration.chat_model,
        )
        self.expose_agent(NAME, agent.as_handler())

    async def run(self) -> None:
        await serve_until_stopped(self)
