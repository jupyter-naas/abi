"""One shared, lazily-connected NATS client for this process.

``nats-py`` is asyncio-only; the engine's own loading sequence
(``Engine.load()``, ``EngineServiceLoader``, ``EngineNATSLoader``) is
synchronous. This bridges the two exactly the way
``naas_abi_core.services.bus.adapters.secondary.NATSJetStreamAdapter`` and
``naas_abi_core.services.object_storage.adapters.secondary.
ObjectStorageSecondaryAdapterNATSClient`` already do: one persistent
background thread running its own event loop, with synchronous callers
submitting work via ``asyncio.run_coroutine_threadsafe(...).result(...)``.

Factored out here rather than a third copy of the same ~30 lines --
``EngineNATSLoader`` needs exactly one shared connection for every primary
adapter it starts, not one per service.

Module-level shared state, mirroring the ``_shared_checkpointer`` pattern in
``naas_abi_core.services.agent.Agent`` (one shared resource per process,
closed at interpreter exit via ``atexit``).
"""

from __future__ import annotations

import asyncio
import atexit
import threading
from threading import Thread

import nats
from naas_abi_core import logger
from nats.aio.client import Client as NATSClient

_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: Thread | None = None
_nc: NATSClient | None = None
_nc_url: str | None = None
_lock = threading.Lock()


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop, _loop_thread
    if _loop is not None and _loop.is_running():
        return _loop

    ready = threading.Event()
    holder: dict[str, asyncio.AbstractEventLoop] = {}

    def _run() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        holder["loop"] = loop
        ready.set()
        loop.run_forever()
        loop.close()

    thread = Thread(target=_run, daemon=True, name="nats-engine-runtime-loop")
    thread.start()
    ready.wait()
    _loop = holder["loop"]
    _loop_thread = thread
    return _loop


def run_coro(coro, timeout: float = 10.0):
    """Run ``coro`` to completion on the shared loop, blocking the calling
    (synchronous) thread until it finishes or raises."""
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=timeout)


def get_connection(nats_url: str, timeout: float = 10.0) -> NATSClient:
    """Return the shared, connected NATS client for this process.

    Connects lazily on first call. Safe to call repeatedly (e.g. once per
    service ``EngineNATSLoader`` exposes) -- later calls with the same
    ``nats_url`` reuse the existing connection; a different ``nats_url``
    replaces it (closing the old one first), the same reconnect-on-change
    behaviour ``Agent.create_checkpointer`` already has for
    ``POSTGRES_URL``.
    """
    global _nc, _nc_url
    with _lock:
        if _nc is not None and _nc.is_connected and _nc_url == nats_url:
            return _nc
        if _nc is not None:
            _close_locked()
        _nc = run_coro(nats.connect(nats_url), timeout=timeout)
        _nc_url = nats_url
        return _nc


def _close_locked() -> None:
    global _nc, _nc_url
    nc = _nc
    _nc = None
    _nc_url = None
    if nc is not None:
        try:
            run_coro(nc.close(), timeout=5.0)
        except Exception:  # noqa: BLE001
            # Best-effort on the way out, mirrors _close_shared_checkpointer.
            logger.opt(exception=True).debug(
                "nats_runtime: error closing shared connection"
            )


def close() -> None:
    """Close the shared connection. Registered via ``atexit`` below; call
    directly too if a caller needs a fresh connection sooner."""
    with _lock:
        _close_locked()

    global _loop, _loop_thread
    loop, thread = _loop, _loop_thread
    _loop, _loop_thread = None, None
    if loop is not None:
        loop.call_soon_threadsafe(loop.stop)
    if thread is not None:
        thread.join(timeout=5.0)


atexit.register(close)
