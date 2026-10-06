"""Whether this engine serves the kernel services, and its handover (NATS mode).

Runs the ownership domain (``naas_abi_core.engine.ownership``) for the
synchronous engine: claim at load, renew while serving, stand by and take over
during a deploy, release at shutdown. See
docs/adr/20261006_single-serving-engine.md.

The lease lives on its own event loop thread and NATS connection, never on
``nats_runtime``'s: a renewal must not wait behind a busy service endpoint,
since a late renewal fences the engine. The engine's callbacks (stop serving,
serve again, start serving after a handover) run in worker threads, where
blocking engine calls are safe.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import signal
import threading
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from naas_abi_core import logger
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
    NATSEngineConfiguration,
)
from naas_abi_core.engine.engine_loaders.EngineJobLoader import LoopThread
from naas_abi_core.engine.ownership.ownership_factory import this_process
from naas_abi_core.engine.ownership.ownership_ports import Holder
from naas_abi_core.engine.ownership.ownership_service import (
    Claim,
    EngineAlreadyServing,
    EngineOwnership,
    OwnershipError,
    require_shared_backends,
)

LOOP_THREAD_NAME = "abi-engine-ownership-loop"
STANDBY_THREAD_NAME = "abi-engine-standby"
CALL_TIMEOUT_SECONDS = 30.0

OwnershipFactory = Callable[
    [NATSEngineConfiguration, Holder], Awaitable[EngineOwnership]
]


def _terminate_process() -> None:
    """Stop this process as an orchestrator would, so it shuts down cleanly."""
    os.kill(os.getpid(), signal.SIGTERM)


def _in_thread(callback: Callable[[], None], name: str) -> Callable[[], Any]:
    async def run() -> None:
        try:
            await asyncio.to_thread(callback)
        except Exception:  # noqa: BLE001 - must not stop the lease renewals
            logger.opt(exception=True).error(f"Engine ownership callback {name} failed")

    return run


class EngineOwnershipLoader:
    def __init__(
        self,
        configuration: NATSConfiguration,
        *,
        environ: Mapping[str, str] | None = None,
        ownership_factory: OwnershipFactory | None = None,
        on_lost: Callable[[], None] = _terminate_process,
        local_backends: Mapping[str, str] | None = None,
        instance_id: str | None = None,
    ):
        """``local_backends``: the owned services whose data stays on this host,
        and where. A deploy (rollout id) refuses to start with any.
        ``instance_id``: the engine's, which the lease is held under."""
        self.configuration = configuration
        self.local_backends = dict(local_backends or {})
        self.settings = configuration.engine.resolved(
            os.environ if environ is None else environ
        )
        # An auto engine never stands by, whatever the rollout.
        self.holder = this_process(
            self.settings.rollout_id if self.settings.role == "serve" else "",
            instance_id,
        )
        self.instance_id = self.holder.instance_id
        self.loop_thread_name = LOOP_THREAD_NAME
        self._factory = ownership_factory or self._jetstream_ownership
        self._on_lost = on_lost
        self._loop: LoopThread | None = None
        self._loop_lock = threading.Lock()
        self._nc: Any = None
        self._ownership: EngineOwnership | None = None
        self._keeping: concurrent.futures.Future | None = None
        self._standby: concurrent.futures.Future | None = None
        self._released = threading.Event()

    # --- the loop --------------------------------------------------------------------------

    def _thread(self) -> LoopThread:
        with self._loop_lock:
            if self._loop is None:
                self._loop = LoopThread(LOOP_THREAD_NAME)
            return self._loop

    def _submit(self, coro: Any) -> concurrent.futures.Future:
        return asyncio.run_coroutine_threadsafe(coro, self._thread().loop)

    def run(self, coro: Any, timeout: float | None = CALL_TIMEOUT_SECONDS) -> Any:
        """Run ``coro`` on the ownership loop and wait for its result."""
        return self._submit(coro).result(timeout)

    async def _jetstream_ownership(
        self, settings: NATSEngineConfiguration, me: Holder
    ) -> EngineOwnership:
        import nats
        from naas_abi_core.engine.nats_naming import connection_name
        from naas_abi_core.engine.ownership.ownership_factory import (
            create_engine_ownership,
        )

        self._nc = await nats.connect(
            self.configuration.nats_url, name=connection_name("abi-engine-ownership")
        )
        return await create_engine_ownership(self._nc, me, settings.timing())

    def _require(self) -> EngineOwnership:
        if self._ownership is None:
            raise OwnershipError("claim() first")
        return self._ownership

    def _lost(self) -> None:
        if not self._released.is_set():
            self._on_lost()

    # --- the engine's calls ----------------------------------------------------------------

    def claim(self) -> Claim | None:
        """Serve now, stand by, or raise ``EngineAlreadyServing``; None for a client.

        May observe the current holder for one lease period first. An auto
        engine is a client when another engine serves.
        """
        if self.settings.role == "client":
            logger.info("Engine role is client: it serves nothing and hosts no jobs")
            return None
        require_shared_backends(self.holder, self.local_backends)

        async def claim() -> Claim:
            self._ownership = await self._factory(self.settings, self.holder)
            return await self._ownership.claim()

        try:
            claimed = self.run(claim(), timeout=None)
        except EngineAlreadyServing as exc:
            if self.settings.role != "auto":
                raise
            logger.info(
                f"Another engine serves ({exc.holder.describe()}): this one is a client"
            )
            return None
        if claimed is Claim.SERVING:
            logger.info(f"This engine serves the kernel services ({self.instance_id})")
        else:
            logger.info(
                f"Standing by for rollout {self.settings.rollout_id}: another "
                "engine serves until it stops"
            )
        return claimed

    def keep(
        self, *, on_fenced: Callable[[], None], on_restored: Callable[[], None]
    ) -> None:
        """Renew in the background; ``on_fenced`` stops serving, ``on_restored``
        serves again. Losing the lease stops the process."""
        self._keeping = self._submit(
            self._require().keep(
                on_fenced=_in_thread(on_fenced, "on_fenced"),
                on_restored=_in_thread(on_restored, "on_restored"),
                on_lost=_in_thread(self._lost, "on_lost"),
            )
        )

    def take_over_in_background(
        self,
        start_serving: Callable[[], None],
        *,
        on_fenced: Callable[[], None],
        on_restored: Callable[[], None],
    ) -> threading.Thread:
        """From standby: once this engine holds the lease, ``start_serving`` and
        keep it. A standby that cannot take over stops the process."""
        standby = self._submit(self._require().wait_for_lease())
        self._standby = standby

        def take_over() -> None:
            try:
                standby.result()
            except concurrent.futures.CancelledError:
                return  # released while standing by
            except Exception as exc:  # noqa: BLE001
                logger.critical(f"The standby engine stops: {exc}")
                self._lost()
                return
            logger.info(
                f"This engine took over the kernel services ({self.instance_id})"
            )
            try:
                start_serving()
            except Exception:  # noqa: BLE001
                logger.opt(exception=True).critical(
                    "The engine took over but could not start serving"
                )
                self._lost()
                return
            self.keep(on_fenced=on_fenced, on_restored=on_restored)

        thread = threading.Thread(
            target=take_over, daemon=True, name=STANDBY_THREAD_NAME
        )
        thread.start()
        return thread

    def release(self) -> None:
        """Stop standing by or renewing, and free the lease if this engine holds it."""
        self._released.set()
        if self._standby is not None:
            self._standby.cancel()
        if self._ownership is None:
            return
        try:
            self.run(self._ownership.release())
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Could not release the engine lease: {exc!r}")
        if self._keeping is not None:
            try:
                self._keeping.result(timeout=CALL_TIMEOUT_SECONDS)
            except Exception:  # noqa: BLE001 - cancelled, or already logged by keep()
                logger.opt(exception=True).debug("The lease renewals ended")

    def close(self) -> None:
        """Release, then close the lease's connection and loop."""
        self.release()
        loop, self._loop = self._loop, None
        if loop is None:
            return
        if self._nc is not None:
            nc, self._nc = self._nc, None
            try:
                asyncio.run_coroutine_threadsafe(nc.close(), loop.loop).result(5.0)
            except Exception:  # noqa: BLE001
                logger.opt(exception=True).debug("Closing the lease connection failed")
        loop.stop()
