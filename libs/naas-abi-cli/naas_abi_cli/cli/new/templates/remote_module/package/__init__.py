"""{{module_name_pascal}}: a remote ABI module.

It runs in its own process (``python -m {{module_name_snake}}``) and reaches the
engine only through NATS, with ``naas-abi-sdk``. It never imports
``naas_abi_core``: the Dockerfile fails the build if core is installed, and
``tests/module_test.py`` checks the import. See AGENTS.md.
"""

from __future__ import annotations

import asyncio
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


@dataclass
class {{module_name_pascal}}Configuration(ModuleConfiguration):
    # Canonical id of a chat model the engine registers; empty: its default.
    chat_model: str = ""


class ABIModule(BaseModule[{{module_name_pascal}}Configuration]):
    Configuration = {{module_name_pascal}}Configuration
    module_id = MODULE_ID
    package_version = "0.1.0"
    # Services this module calls on the engine. Undeclared ones are refused.
    dependencies = ModuleDependencies(services=("model_registry", "document"))
    # Published in discovery; Nexus lists them with the engine's agents.
    agents = (AgentDescriptor(NAME, DESCRIPTION, capabilities=AGENT_INVOKE),)

    async def on_initialized(self) -> None:
        # Runs once the engine's services are reachable, before the module is
        # READY: bind every agent declared above here.
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
        await asyncio.Event().wait()
