"""{{module_name_pascal}}: a remote ABI module.

It runs in its own process (``python -m {{module_name_snake}}``) and reaches the
engine only through NATS, with ``naas-abi-sdk``. It never imports
``naas_abi_core``: the Dockerfile fails the build if core is installed, and
``tests/module_test.py`` checks the import. See AGENTS.md.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from naas_abi_sdk import (
    AgentDescriptor,
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_sdk.jobs import Every, JobContext, job

from {{module_name_snake}} import jobs
from {{module_name_snake}}.agents.{{module_name_pascal}}Agent import (
    DESCRIPTION,
    NAME,
    create_agent,
)

# Stable across replicas and restarts: discovery, job subjects and the agent's
# memory are keyed by it. Changing it starts the module over.
MODULE_ID = "{{module_id}}"
# Remote callers (Nexus, other modules) invoke the agent through this capability.
AGENT_INVOKE = ("agent.invoke.v1",)

logger = logging.getLogger(__name__)
# While discovery has not made the module READY, run() says so this often.
NOT_READY_NOTICE_SECONDS = 15.0


@dataclass
class {{module_name_pascal}}Configuration(ModuleConfiguration):
    # Canonical id of a chat model the engine registers; empty: its default.
    chat_model: str = ""


class ABIModule(BaseModule[{{module_name_pascal}}Configuration]):
    Configuration = {{module_name_pascal}}Configuration
    module_id = MODULE_ID
    package_version = "0.1.0"
    # Services this module calls on the engine. Undeclared ones are refused.
    # triple_store: ontologies/ is sent to the engine's schema graph through it.
    dependencies = ModuleDependencies(
        services=("model_registry", "document", "triple_store")
    )
    # Published in discovery; Nexus lists them with the engine's agents.
    agents = (AgentDescriptor(NAME, DESCRIPTION, capabilities=AGENT_INVOKE),)

    async def on_initialized(self) -> None:
        # Runs once the engine's services are reachable, before the module is
        # READY: bind every agent declared above here. Workflows and pipelines
        # (workflows/, pipelines/) are built after this hook; an agent takes its
        # tools when it is built, so build them first to give it theirs:
        #     await self.build_processes()
        #     tools = self.get_workflow("my_workflow").as_tools()
        # and pass `tools=tools` to create_agent.
        agent = await create_agent(
            self.engine, MODULE_ID, chat_model=self.configuration.chat_model
        )
        self.expose_agent(NAME, agent.as_handler())

    @job(triggers=(Every("1h"),), timeout=timedelta(minutes=5))
    async def heartbeat(self, ctx: JobContext) -> dict[str, Any]:
        """Hourly example job: JetStream schedules it, this process runs it."""
        return await jobs.heartbeat(self, ctx)

    async def run(self) -> None:
        # Agents and jobs are served in the background; stay up until stopped.
        # SIGTERM drains the module: it finishes running work and unregisters.
        loop = asyncio.get_running_loop()
        started = loop.time()
        notice = started + NOT_READY_NOTICE_SECONDS
        while (status := self.discovery_status) != "READY":
            if loop.time() >= notice:  # say why nothing happens yet
                logger.warning(
                    "%s not READY after %.0f s (discovery status %s): is the "
                    "engine's discovery running, and ABI_MODULE_KEY this module's?",
                    MODULE_ID,
                    loop.time() - started,
                    status,
                )
                notice += NOT_READY_NOTICE_SECONDS
            await asyncio.sleep(min(0.5, NOT_READY_NOTICE_SECONDS))
        logger.info("%s READY: registered in discovery, serving %s", MODULE_ID, NAME)
        await asyncio.Event().wait()
