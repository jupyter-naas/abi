"""GitHub: a remote ABI module (REST and GraphQL APIs).

Runs in its own process (``python -m naas_abi_apps.github``) and reaches the
engine only through NATS. Replaces the in-engine
``naas_abi_marketplace.applications.github`` (still imported in-process by the
in-engine ``support`` module, see jupyter-naas/abi#1423). The token is the
``GITHUB_ACCESS_TOKEN`` engine secret, read at start. ``ontologies/`` goes to
the engine's schema graph.

Everyone who may use the agent acts with that one token, so the agent reads,
and writes only through the tools ``GITHUB_AGENT_WRITE_TOOLS`` names, within
``GITHUB_REPOSITORIES`` when set.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from naas_abi_apps.common.agents import read_secrets, secret_key
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
    # Everyone who may use the GitHub agent acts with this module's token. The
    # agent carries the read tools (READ_TOOLS) and, besides, only the write
    # tools named here (comma-separated, e.g. "github_create_issue").
    agent_write_tools: str = ""
    # When set, the agent reaches only these repositories (comma-separated
    # "owner/repo").
    repositories: str = ""

    def write_tools(self) -> set[str]:
        return {
            name.strip() for name in self.agent_write_tools.split(",") if name.strip()
        }

    def repository_list(self) -> list[str] | None:
        names = [name.strip() for name in self.repositories.split(",") if name.strip()]
        return names or None


class ABIModule(BaseModule[GitHubConfiguration]):
    Configuration = GitHubConfiguration
    module_id = MODULE_ID
    package_version = "0.1.0"
    dependencies = ModuleDependencies(
        services=("model_registry", "document", "secret", "triple_store")
    )
    agents = (AgentDescriptor(NAME, DESCRIPTION, capabilities=AGENT_INVOKE),)

    async def on_initialized(self) -> None:
        name = self.configuration.access_token_secret
        token = (await read_secrets(self.engine, {"token": name}, module_id=MODULE_ID))[
            "token"
        ]
        if not token:
            logger.warning(
                "%s: secret %s not set; no GitHub tools",
                MODULE_ID,
                secret_key(MODULE_ID, name),
            )
        agent = await create_agent(
            self.engine,
            MODULE_ID,
            access_token=token,
            chat_model=self.configuration.chat_model,
            write_tools=self.configuration.write_tools(),
            repositories=self.configuration.repository_list(),
        )
        self.expose_agent(NAME, agent.as_handler())

    async def run(self) -> None:
        await serve_until_stopped(self)
