"""The engine's services for the X module's synchronous code.

The X module keeps its large synchronous bodies (graph mapping, dataset
projection, app snapshots) as they were in-engine. They are CPU-bound, so they
run in worker threads (``asyncio.to_thread``), never on the module's event
loop. From there they reach the engine through ``SyncModule``: the module's
configuration, and ``engine.services.<service>`` whose methods are the SDK's,
blocking until the call finished on the module's loop::

    sync = module.sync                       # built in ABIModule.on_initialized
    await sync.call(body, sync, ...)         # on the module's own threads

    def body(module, ...):                   # in a worker thread
        module.engine.services.object_storage.put_object("x", "a.json", b"{}")
        module.run(integration.search_recent_tweets(...))   # any coroutine

A blocking call made on the loop itself would wait for itself forever:
``Blocking`` raises instead. The bodies run on threads of their own
(``SyncModule.call``), not on the loop's default executor: a body waits there
for the loop, and the loop resolves host names (httpx) on its default
executor, so many bodies at once would starve the very calls they wait for.
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import inspect
import json
import logging
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, TypeVar

from naas_abi_sdk.services.errors import ObjectNotFound, ServiceError

T = TypeVar("T")

logger = logging.getLogger("naas_abi_apps.x")

# Threads of the synchronous bodies (flows, app requests, agent tools).
SYNC_THREADS = 32

__all__ = [
    "Blocking",
    "DatasetAlreadyExists",
    "DatasetNotFound",
    "ObjectNotFound",
    "StorageUtils",
    "SyncModule",
    "SyncService",
    "dataset_error",
    "logger",
    "results_to_list",
]


class Blocking:
    """Run a coroutine on the module's loop and wait for it, from a worker thread."""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    def __call__(self, coro: Awaitable[T], timeout: float | None = None) -> T:
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self.loop:
            if inspect.iscoroutine(coro):
                coro.close()
            raise RuntimeError(
                "A blocking X service call on the module's event loop would wait "
                "for itself: run the synchronous body with asyncio.to_thread"
            )
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)  # type: ignore[arg-type]


class SyncService:
    """An SDK service whose coroutine methods block (``Blocking``); other
    attributes are the service's own."""

    def __init__(self, service: Any, run: Callable[[Awaitable[Any]], Any]):
        self._service = service
        self._run = run

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._service, name)
        if not inspect.iscoroutinefunction(attr):
            return attr

        def call(*args: Any, **kwargs: Any) -> Any:
            return self._run(attr(*args, **kwargs))

        call.__name__ = name
        return call


class _SyncServices:
    def __init__(self, services: Any, run: Callable[[Awaitable[Any]], Any]):
        self._services = services
        self._run = run
        self._wrapped: dict[str, SyncService] = {}

    def __getattr__(self, name: str) -> Any:
        if name.endswith("_available") or name.startswith("_"):
            return getattr(self._services, name)
        wrapped = self._wrapped.get(name)
        if wrapped is None:
            wrapped = self._wrapped[name] = SyncService(
                getattr(self._services, name), self._run
            )
        return wrapped


class SyncModule:
    """The view of the X module its synchronous bodies take as ``module``:
    ``configuration``, ``engine.services`` (blocking), ``run(coro)``; any other
    attribute is the module's."""

    def __init__(
        self,
        module: Any,
        loop: asyncio.AbstractEventLoop,
        *,
        threads: int = SYNC_THREADS,
    ):
        self._module = module
        self._loop = loop
        self.run = Blocking(loop)
        self.engine = SimpleNamespace(
            services=_SyncServices(module.engine.services, self.run)
        )
        self.executor = ThreadPoolExecutor(
            max_workers=threads, thread_name_prefix="x-sync"
        )

    async def call(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """``fn(*args, **kwargs)`` on the module's own threads, in a copy of the
        caller's context (as ``asyncio.to_thread``): use it for every
        synchronous body, never the loop's default executor."""
        context = contextvars.copy_context()
        return await self._loop.run_in_executor(
            self.executor, functools.partial(context.run, fn, *args, **kwargs)
        )

    def threaded(self, fn: Callable[..., T]) -> Callable[..., Awaitable[T]]:
        """``fn`` as an async function running on the module's threads: what
        ``ctx.step`` takes for a synchronous body (given a sync function, the
        SDK would run it on the loop's default executor)."""

        async def on_threads(*args: Any, **kwargs: Any) -> T:
            return await self.call(fn, *args, **kwargs)

        on_threads.__name__ = getattr(fn, "__name__", "body")
        return on_threads

    def close(self) -> None:
        """Stop taking work; running bodies finish on their threads."""
        self.executor.shutdown(wait=False, cancel_futures=True)

    @property
    def configuration(self) -> Any:
        return self._module.configuration

    @property
    def module(self) -> Any:
        """The SDK module itself (async API; never block on it from here)."""
        return self._module

    def __getattr__(self, name: str) -> Any:
        return getattr(self._module, name)


# --- object storage helpers (core's StorageUtils, the methods X uses) ----------------


class StorageUtils:
    """Core's ``StorageUtils`` methods the X code uses, over a blocking object
    storage (``module.engine.services.object_storage``)."""

    def __init__(self, storage: Any):
        self._storage = storage

    def _copy(self, dir_path: str, file_name: str, content: bytes) -> None:
        stamped = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}_{file_name}"
        try:
            self._storage.put_object(dir_path, stamped, content)
        except Exception as e:  # noqa: BLE001 - a copy never fails the save
            logger.error(f"Error making copy in {dir_path}: {e}")

    def save_text(
        self,
        text: str,
        dir_path: str,
        file_name: str,
        encoding: str = "utf-8",
        copy: bool = True,
    ) -> tuple[str, str]:
        content = text.encode(encoding)
        self._storage.put_object(dir_path, file_name, content)
        if copy:
            self._copy(dir_path, file_name, content)
        return dir_path, file_name

    def get_text(
        self, dir_path: str, file_name: str, encoding: str = "utf-8"
    ) -> str | None:
        try:
            return self._storage.get_object(dir_path, file_name).decode(encoding)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Error getting text from {dir_path}: {e}")
            return None

    def save_json(
        self, data: dict | list, dir_path: str, file_name: str, copy: bool = True
    ) -> tuple[str, str]:
        content = json.dumps(data, indent=4, ensure_ascii=False).encode("utf-8")
        self._storage.put_object(dir_path, file_name, content)
        if copy:
            self._copy(dir_path, file_name, content)
        return dir_path, file_name

    def get_json(self, dir_path: str, file_name: str) -> dict:
        try:
            return json.loads(self._storage.get_object(dir_path, file_name))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Error getting JSON data from {dir_path}: {e}")
            return {}


# --- triple store and dataset helpers ------------------------------------------------


def results_to_list(results: Any) -> list[dict] | None:
    """Core's ``SPARQLUtils.results_to_list``: rows as ``{label: str | None}``,
    ``None`` when there are none."""
    data = [
        {key: str(row[key]) if row[key] else None for key in row.labels}
        for row in results
    ]
    return data or None


DatasetNotFound = "DATASET_NOT_FOUND"
DatasetAlreadyExists = "DATASET_ALREADY_EXISTS"


def dataset_error(error: BaseException, code: str) -> bool:
    """Whether ``error`` is the dataset service's ``code`` (``DatasetNotFound``,
    ``DatasetAlreadyExists``): over NATS they are ``ServiceError``s."""
    return isinstance(error, ServiceError) and getattr(error, "code", "") == code
