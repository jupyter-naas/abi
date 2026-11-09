"""``python -m {{module_name_snake}}``: run the module until it is stopped.

Environment (``abi dev up`` and the Compose service set the first three):

- ``ABI_NATS_URL``: the broker (``nats://host:4222``), no login in it;
- ``ABI_SERVICE_KEY``: this module's service key (``abi_sk_...``), of the
  account ``module/<project>/{{module_id}}``. It logs in to the broker and is
  exchanged for the engine's tokens; the module holds no signing secret.
  ``abi dev up`` creates it; elsewhere ``abi iam service-account create
  module/<project>/{{module_id}} --key``;
- ``ABI_DISCOVERY_PROJECT``: the project whose engine hosts discovery;
- ``{{module_name_upper}}_CHAT_MODEL``: a chat model id (default: the engine's);
- ``ABI_HEALTH_PORT``: opens ``/health`` and ``/ready`` probes;
- ``OTEL_EXPORTER_OTLP_ENDPOINT``: exports traces;
- ``LOG_LEVEL`` (default ``INFO``).
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from collections.abc import Awaitable, Mapping
from typing import TypeVar

from naas_abi_sdk import DiscoveryConfiguration, run_module

from {{module_name_snake}} import ABIModule

DEFAULT_NATS_URL = "nats://127.0.0.1:4222"
DEFAULT_DISCOVERY_PROJECT = "{{discovery_project}}"

T = TypeVar("T")


async def run_until_signalled(work: Awaitable[T]) -> T | None:
    """Run ``work``; on SIGTERM/SIGINT cancel it and return None.

    Once the module is running, ``run_module`` takes over both signals: it
    drains (finishes the runs it started) and unregisters. Before that, while
    it waits for the engine, Python would die on SIGTERM without cleanup and
    the registration would linger until its lease expires. Cancelling instead
    runs that cleanup, so callers stop routing to the module at once.
    """
    loop = asyncio.get_running_loop()
    task = asyncio.ensure_future(work)
    stopped = False

    def stop() -> None:
        nonlocal stopped
        stopped = True
        task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop)
    try:
        return await task
    except asyncio.CancelledError:
        if stopped:
            return None
        raise
    finally:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)


def configuration_from(env: Mapping[str, str]) -> ABIModule.Configuration:
    return ABIModule.Configuration(
        chat_model=env.get("{{module_name_upper}}_CHAT_MODEL", "")
    )


def main(env: Mapping[str, str] = os.environ) -> int:
    logging.basicConfig(
        level=env.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    key = env.get("ABI_SERVICE_KEY", "")
    if not key.startswith("abi_sk_"):
        raise SystemExit(
            "Set ABI_SERVICE_KEY to this module's service key (abi_sk_...): "
            "abi iam service-account create module/<project>/{{module_id}} --key"
        )
    asyncio.run(
        run_until_signalled(
            run_module(
                ABIModule,
                url=env.get("ABI_NATS_URL") or DEFAULT_NATS_URL,
                token=key,
                configuration=configuration_from(env),
                # Model calls stream, but each exchange can take a while.
                timeout=60,
                discovery=DiscoveryConfiguration(
                    project=env.get("ABI_DISCOVERY_PROJECT")
                    or DEFAULT_DISCOVERY_PROJECT,
                    # The engine may still be booting (its first start loads
                    # every module and ontology).
                    startup_timeout=300,
                ),
            )
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
