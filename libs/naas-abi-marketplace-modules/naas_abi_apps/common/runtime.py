"""What every remote application module does the same way: wait for READY,
handle signals before ``run_module`` takes over, and run from the environment.

Environment of ``python -m naas_abi_apps.<app>``:

- ``ABI_NATS_URL``: the broker, logged in as the user ``module``;
- ``ABI_DISCOVERY_PROJECT``: the project whose engine hosts discovery;
- ``ABI_MODULE_KEY`` (or ``ABI_SERVICE_TOKEN``): signs the module's tokens;
- ``<APP>_<FIELD>``: a configuration field, e.g. ``PENNYLANE_CHAT_MODEL``;
- ``ABI_HEALTH_PORT``, ``OTEL_EXPORTER_OTLP_ENDPOINT``, ``LOG_LEVEL``.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import os
import signal
from collections.abc import Awaitable, Mapping
from typing import Any, TypeVar

from naas_abi_sdk import DiscoveryConfiguration, run_module
from naas_abi_sdk.service_token import ModuleToken, token_from_env

DEFAULT_NATS_URL = "nats://127.0.0.1:4222"
DEFAULT_DISCOVERY_PROJECT = "default"
NOT_READY_NOTICE_SECONDS = 15.0

T = TypeVar("T")
logger = logging.getLogger(__name__)


async def serve_until_stopped(
    module: Any, *, notice_seconds: float | None = None
) -> None:
    """``ABIModule.run``: log READY (or why not yet), then wait to be stopped.

    Agents, jobs and workflows are served in the background. SIGTERM drains the
    module: it finishes running work and unregisters.
    """
    every = NOT_READY_NOTICE_SECONDS if notice_seconds is None else notice_seconds
    loop = asyncio.get_running_loop()
    started = loop.time()
    notice = started + every
    while (status := module.discovery_status) != "READY":
        if loop.time() >= notice:
            logger.warning(
                "%s not READY after %.0f s (discovery status %s): is the "
                "engine's discovery running, and ABI_MODULE_KEY this module's?",
                module.module_id,
                loop.time() - started,
                status,
            )
            notice += every
        await asyncio.sleep(min(0.5, every))
    logger.info(
        "%s READY: registered in discovery, serving %s",
        module.module_id,
        ", ".join(agent.name for agent in module.agents) or "no agent",
    )
    await asyncio.Event().wait()


async def run_until_signalled(work: Awaitable[T]) -> T | None:
    """Run ``work``; on SIGTERM/SIGINT cancel it and return None.

    Once the module runs, ``run_module`` handles both signals (drain, then
    unregister). Before that, cancelling still runs its cleanup, so a module
    stopped while it waits for the engine does not linger in discovery.
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


def configuration_from(
    configuration_class: type, prefix: str, env: Mapping[str, str]
) -> Any:
    """The module configuration: each string field from ``<PREFIX>_<FIELD>``
    when set, else its default. Secrets never come from here: modules read
    them from the engine's ``secret`` service."""
    values = {}
    for field in dataclasses.fields(configuration_class):
        variable = f"{prefix}_{field.name}".upper()
        if variable in env:
            values[field.name] = env[variable]
    return configuration_class(**values)


def token_from(env: Mapping[str, str], module_id: str) -> str | ModuleToken:
    """The module calls the engine as itself: a token for its module id."""
    return token_from_env(env, module_id)


def main(
    module_class: Any, env_prefix: str, env: Mapping[str, str] = os.environ
) -> int:
    """``python -m naas_abi_apps.<app>``: run the module until it is stopped."""
    logging.basicConfig(
        level=env.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(
        run_until_signalled(
            run_module(
                module_class,
                url=env.get("ABI_NATS_URL") or DEFAULT_NATS_URL,
                token=token_from(env, module_class.module_id),
                configuration=configuration_from(
                    module_class.Configuration, env_prefix, env
                ),
                # Model calls stream, but each exchange can take a while.
                timeout=60,
                discovery=DiscoveryConfiguration(
                    project=env.get("ABI_DISCOVERY_PROJECT")
                    or DEFAULT_DISCOVERY_PROJECT,
                    # The engine may still be booting.
                    startup_timeout=300,
                ),
            )
        )
    )
    return 0
