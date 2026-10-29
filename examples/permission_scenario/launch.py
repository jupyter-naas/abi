"""Run a scenario module as ``abi dev up`` starts it: its key in
``ABI_SERVICE_KEY``, the broker in ``ABI_NATS_URL``, discovery's project in
``ABI_DISCOVERY_PROJECT``."""

from __future__ import annotations

import asyncio
import logging
import os

from naas_abi_sdk import DiscoveryConfiguration, run_module


def run_until_stopped(module_type: type) -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    asyncio.run(
        run_module(
            module_type,
            url=os.environ.get("ABI_NATS_URL", "nats://127.0.0.1:4222"),
            token=os.environ["ABI_SERVICE_KEY"],
            timeout=60,
            discovery=DiscoveryConfiguration(
                project=os.environ.get("ABI_DISCOVERY_PROJECT", "abi"),
                # The engine's first start loads every module and ontology.
                startup_timeout=300,
            ),
        )
    )
