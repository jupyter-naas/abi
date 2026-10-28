"""M, Market Intelligence's stand-in: one app, ``prices`` (``apps/prices``)."""

from __future__ import annotations

import asyncio

from naas_abi_sdk import BaseModule, ModuleDependencies


class ABIModule(BaseModule):
    module_id = "dev.market"
    package_version = "0.1.0"
    # A manifest holds at least one statement: its own documents.
    dependencies = ModuleDependencies(services=("document",))

    async def run(self) -> None:
        # Its agents and apps are served in the background: stay up until stopped.
        await asyncio.Event().wait()
