"""Fakes for the flow tests: an async context that journals steps the way the
SDK's ``FlowContext`` does, so a test can run a handler twice and see what a
retry does not repeat, and a module with the configuration the flows read."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from naas_abi_apps.common.testing import fake_engine
from naas_abi_apps.x import MODULE_ID, ABIModule
from naas_abi_apps.x.configuration import (
    XConfiguration,
    XSearchRecentTweetsFilesConfiguration,
    XTweetSearchWorkflowConfiguration,
)
from naas_abi_apps.x.x_proxy.testing import (
    ON_SYNC_THREAD,
    ThreadedSync,
    on_sync_thread,
)
from naas_abi_sdk.jobs import is_async_callable
from naas_abi_sdk.workflows import encode_result


class FakeFlowContext:
    """The SDK ``FlowContext`` as the bodies use it.

    ``step`` journals by key (in ``journal``, which outlives one attempt), runs a
    sync function as the SDK does (``asyncio.to_thread``, the loop's default
    executor), awaits an async one, and keeps its result as JSON within the SDK's
    cap; ``off_loop[key]`` says whether the body ran on the module's ``x-sync``
    threads (``module.sync.threaded``), never true for a bare sync function;
    ``call`` asks ``children(workflow, input)`` (which may raise
    ``ChildRunFailed``) and journals what it returns. A key used twice in one
    attempt raises, as in the SDK."""

    def __init__(
        self,
        *,
        job: str = "search_recent_tweets",
        run_id: str = "search_recent_tweets:10",
        module_id: str = MODULE_ID,
        journal: dict[str, Any] | None = None,
        children: Callable[[str, dict[str, Any]], Any] | None = None,
        payload: dict[str, Any] | None = None,
        attempt: int = 1,
    ):
        self.job, self.run_id, self.attempt = job, run_id, attempt
        self.payload = payload or {}
        self.journal = journal if journal is not None else {}
        self.children = children or (lambda workflow, payload: {"ok": True})
        self.runtime = SimpleNamespace(module_id=module_id, project="default")
        self.cancelled = asyncio.Event()
        self.skipped: str | None = None
        self.logs: list[str] = []
        self.ran: list[str] = []  # steps and calls that really ran, in order
        self.called: list[tuple[str, str, Any]] = []
        self.off_loop: dict[str, bool] = {}  # sync step key -> ran off the loop
        self._used: set[str] = set()
        self._auto_calls = 0

    @property
    def stages(self) -> list[str]:
        """The steps that really ran, a fan-out's ``key[i]`` collapsed to ``key``."""
        return list(dict.fromkeys(k.split("[")[0] for k in self.ran))

    def _claim(self, key: str) -> None:
        if key in self._used:
            raise ValueError(f"step key {key!r} used twice in one attempt")
        self._used.add(key)

    async def step(self, key, fn, *args, retries=0, backoff=1.0, **kwargs):
        self._claim(key)
        if key in self.journal:
            return self.journal[key]

        def record() -> None:
            self.off_loop[key] = on_sync_thread()

        if is_async_callable(fn):
            # ``module.sync.threaded(body)``: the body runs on the module's
            # threads, where ``ThreadedSync`` calls ``record``.
            token = ON_SYNC_THREAD.set(record)
            try:
                value = await fn(*args, **kwargs)
            finally:
                ON_SYNC_THREAD.reset(token)
        else:
            # As the SDK: a sync function goes to the loop's default executor
            # (``asyncio.to_thread``), which is not the module's pool.
            def call() -> Any:
                record()
                return fn(*args, **kwargs)

            value = await asyncio.to_thread(call)
            if inspect.isawaitable(value):
                value = await value
        value = json.loads(encode_result(key, value))
        self.ran.append(key)
        self.journal[key] = value
        return value

    async def call(self, module_id, workflow, input=None, key=None):
        if key is None:
            self._auto_calls += 1
            key = f"call:{module_id}.{workflow}#{self._auto_calls}"
        self._claim(key)
        if key in self.journal:
            return self.journal[key]
        self.ran.append(key)
        self.called.append((module_id, workflow, input))
        value = self.children(workflow, input)
        if inspect.isawaitable(value):
            value = await value
        self.journal[key] = value
        return value

    def skip(self, reason=""):
        self.skipped = reason

    def log(self, message):
        self.logs.append(message)


def search_filter(
    name: str = "news", **overrides: Any
) -> XTweetSearchWorkflowConfiguration:
    return XTweetSearchWorkflowConfiguration(
        name=name, query=f"{name} lang:en", **overrides
    )


def x_module(
    *filters: XTweetSearchWorkflowConfiguration,
    files: list[XSearchRecentTweetsFilesConfiguration] | None = None,
    **services: Any,
) -> Any:
    """A module with the configuration the flows read and its ``sync`` view
    (``ThreadedSync``: ``call`` / ``threaded`` on ``x-sync`` threads), whose
    ``engine.services`` are the (blocking) ``services`` given."""
    configuration = XConfiguration(
        search_recent_tweets_workflow=list(filters),
        search_recent_tweets_files=list(files or []),
    )
    engine = SimpleNamespace(services=SimpleNamespace(**services))
    sync = ThreadedSync(configuration=configuration, engine=engine, run=None)
    module = SimpleNamespace(
        module_id=MODULE_ID,
        configuration=configuration,
        engine=engine,
        sync=sync,
        bearer_token="token",
    )
    sync.module = module
    return module


def real_x_module(
    *filters: XTweetSearchWorkflowConfiguration,
    files: list[XSearchRecentTweetsFilesConfiguration] | None = None,
) -> ABIModule:
    """The real ``ABIModule`` with its workflows and jobs declared, as ``on_load``
    does, on a fake engine (no broker)."""
    configuration = ABIModule.Configuration(
        search_recent_tweets_workflow=list(filters),
        search_recent_tweets_files=list(files or []),
    )
    module = ABIModule(fake_engine(), configuration)
    module.on_load()
    return module
