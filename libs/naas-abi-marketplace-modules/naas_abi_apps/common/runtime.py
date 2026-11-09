"""What every remote application module does the same way: wait for READY,
handle signals before ``run_module`` takes over, and run from the environment.

Environment of ``python -m naas_abi_apps.<app>``:

- ``ABI_NATS_URL``: the broker (``nats://host:4222``), no login in it;
- ``ABI_SERVICE_KEY``: the module's service key (``abi_sk_...``), of the
  account ``module/<project>/<module id>``. It logs in to the broker and is
  exchanged for the engine's tokens. ``abi dev up`` creates it; elsewhere
  ``abi iam service-account create module/<project>/<module id> --key``, then
  ``abi iam module approve`` once the module has submitted its manifest;
- ``ABI_DISCOVERY_PROJECT``: the project whose engine hosts discovery;
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

DEFAULT_NATS_URL = "nats://127.0.0.1:4222"
DEFAULT_DISCOVERY_PROJECT = "default"
SERVICE_KEY_PREFIX = "abi_sk_"
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
                "engine's discovery running, ABI_SERVICE_KEY this module's, "
                "and its manifest approved (abi iam module approve)?",
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
    """The module configuration: each field from ``<PREFIX>_<FIELD>`` when set,
    else its default (a ``bool`` field reads ``1/true/yes/on`` as true, any
    other value as false). Secrets never come from here: modules read them
    from the engine's ``secret`` service."""
    values: dict[str, Any] = {}
    for field in dataclasses.fields(configuration_class):
        variable = f"{prefix}_{field.name}".upper()
        if variable in env:
            value: Any = env[variable]
            if field.type in (bool, "bool"):
                value = value.strip().lower() in ("1", "true", "yes", "on")
            values[field.name] = value
    return configuration_class(**values)


def service_key(env: Mapping[str, str], module_id: str) -> str:
    """The module's service key: it holds a key, never a signing secret, so
    without one it does not start."""
    key = env.get("ABI_SERVICE_KEY", "")
    if not key.startswith(SERVICE_KEY_PREFIX):
        raise SystemExit(
            "Set ABI_SERVICE_KEY to this module's service key (abi_sk_...): "
            f"abi iam service-account create module/<project>/{module_id} --key"
        )
    return key


def main(
    module_class: Any, env_prefix: str, env: Mapping[str, str] = os.environ
) -> int:
    """``python -m naas_abi_apps.<app>``: run the module until it is stopped."""
    logging.basicConfig(
        level=env.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    key = service_key(env, module_class.module_id)
    asyncio.run(
        run_until_signalled(
            run_module(
                module_class,
                url=env.get("ABI_NATS_URL") or DEFAULT_NATS_URL,
                token=key,
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
