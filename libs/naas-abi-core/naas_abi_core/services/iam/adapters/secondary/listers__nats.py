"""The listers remote modules serve, asked over NATS as the engine
(``AGENTS.md``, "Publishers and listing").

A module that lists a type of its catalog names it in its discovery descriptor
(``ModuleDescriptor.listers``) and serves ``abi.mod.<project>.<sa>.<instance>.iam.list``
(the SDK's ``listers.ListerHost``). For a type of module ``M``'s catalog, IAM gets
a lister here that asks a ready instance of ``M`` naming the type; with none, the
type is offered as wildcards. What a module answers is a list of candidates: IAM
filters it as the caller before anyone sees it.

``list_resources`` is synchronous (IAM is) and runs on the engine's shared NATS
loop (``engine.nats_runtime``), like the built-in IdP's app client.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from naas_abi_core.services.iam.adapters.iam_nats_codec import listed_from_pb
from naas_abi_core.services.iam.listing import (
    ListedPage,
    ListerDirectory,
    ListingQuery,
    ResourceLister,
)

TIMEOUTS = (TimeoutError, asyncio.TimeoutError, concurrent.futures.TimeoutError)
# Discovery is read at most this often.
SNAPSHOT_SECONDS = 10.0
TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class ListerInstance:
    """A ready instance of a module and the types it lists."""

    module_id: str
    service_account: str
    instance_id: str
    listers: frozenset[str]


Instances = Callable[[], Awaitable[list[ListerInstance]]]


class ListerUnavailableError(RuntimeError):
    """No instance answered: the type is offered as wildcards."""


class NATSModuleListers(ListerDirectory):
    def __init__(
        self,
        *,
        nats_url: str,
        project: str,
        token: Callable[[], str],
        host_token: Callable[[str], str],
        timeout: float = TIMEOUT_SECONDS,
        run: Callable[..., Any] | None = None,
        instances: Instances | None = None,
    ) -> None:
        """``run``: how a coroutine runs to completion from this thread (the
        engine's NATS runtime by default). ``instances``: the ready instances and
        what they list (discovery's by default)."""
        self._url, self._project = nats_url, project
        self._token, self._host_token = token, host_token
        self._timeout = timeout
        self._run = run
        self._instances = instances
        self._client: tuple[Any, Any] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._snapshot: tuple[float, list[ListerInstance]] | None = None

    def lister(self, module: str, service: str, type: str) -> ResourceLister | None:
        found = [
            i for i in self._run_sync(self._ready()) if i.module_id == module and type in i.listers
        ]
        if not found:
            return None
        return _RemoteLister(self, found)

    def close(self) -> None:
        """Close the connection it opened, if any (the engine's shutdown)."""
        client, self._client = self._client, None
        if client is not None:
            self._run_sync(client[0].close())

    # -- the engine's NATS loop --------------------------------------------------------

    def _run_sync(self, coroutine: Awaitable[Any]) -> Any:
        if self._run is not None:
            return self._run(coroutine, timeout=self._timeout + 5)
        from naas_abi_core.engine import nats_runtime

        return nats_runtime.run_coro(coroutine, timeout=self._timeout + 5)

    def _clients(self) -> tuple[Any, Any]:
        loop = asyncio.get_running_loop()
        if self._client is None or self._loop is not loop:
            from naas_abi_sdk.discovery import DiscoveryClient
            from naas_abi_sdk.transport import Transport

            transport = Transport(
                self._url,
                self._token,
                timeout=self._timeout,
                host_token=self._host_token,  # type: ignore[arg-type]
            )
            self._client = (transport, DiscoveryClient(transport, self._project))
            self._loop = loop
            self._snapshot = None
        return self._client

    async def _ready(self) -> list[ListerInstance]:
        if self._instances is not None:
            return await self._instances()
        now = time.monotonic()
        if self._snapshot is not None and now - self._snapshot[0] < SNAPSHOT_SECONDS:
            return list(self._snapshot[1])
        _, discovery = self._clients()
        found: list[ListerInstance] = []
        after = ""
        while True:
            page, after = await discovery.list_modules(limit=100, after_instance_id=after)
            for instance in page:
                listers = frozenset(getattr(instance, "listers", ()) or ())
                if instance.status == "READY" and listers:
                    found.append(
                        ListerInstance(
                            instance.module_id,
                            instance.service_account,
                            instance.instance_id,
                            listers,
                        )
                    )
            if not after:
                break
        self._snapshot = (now, found)
        return list(found)

    async def _ask(self, instance: ListerInstance, query: ListingQuery) -> ListedPage:
        from naas_abi_proto.discovery.v1 import discovery_pb2 as pb
        from naas_abi_sdk.listers import call_lister

        transport = self._transport()
        answer = await call_lister(
            transport,
            self._project,
            instance.instance_id,
            pb.ListerQuery(
                service=query.service,
                type=query.type,
                container=query.container,
                text=query.text,
                after=query.after,
                limit=query.limit,
            ),
            service_account=instance.service_account,
        )
        return ListedPage(
            tuple(listed_from_pb(item) for item in answer.items), more=answer.more
        )

    def _transport(self) -> Any:
        return self._clients()[0]

    def ask(self, instances: list[ListerInstance], query: ListingQuery) -> ListedPage:
        """One instance's answer, another's when it does not answer."""

        async def first() -> ListedPage:
            from nats.errors import NoRespondersError

            from naas_abi_sdk.transport import RPCError

            last = "no instance answered"
            for instance in random.sample(instances, min(len(instances), 2)):
                try:
                    return await self._ask(instance, query)
                except (RPCError, NoRespondersError, *TIMEOUTS) as exc:
                    last = str(exc) or type(exc).__name__
                    self._snapshot = None  # that instance is gone or going
            raise ListerUnavailableError(f"{query.service}:{query.type}: {last}")

        return self._run_sync(first())  # type: ignore[no-any-return]


class _RemoteLister(ResourceLister):
    def __init__(self, directory: NATSModuleListers, instances: list[ListerInstance]) -> None:
        self._directory, self._instances = directory, instances

    def list_resources(self, query: ListingQuery) -> ListedPage:
        return self._directory.ask(self._instances, query)
