"""Reads the serving engine's tool catalog over NATS (``IToolCatalogPort``).

For an engine that does not serve (a client or a standby engine): its own
``ToolRegistryService`` publishes and resolves locally and reads the catalog
through this client (``configure_catalog``). Calls are read only, as the engine's
own process (a first-party identity), so the serving engine shows them every
tool; the registry then applies its caller's scopes to what comes back.

The connection opens on first use: an engine that never reads the catalog (the
serving engine is wired with one, then drops it) never builds a transport.
Failures are ``ToolCatalogError``s, never a bare ``ValueError`` or RPC error.
"""

from __future__ import annotations

import threading

from naas_abi_core import logger
from naas_abi_core.engine import nats_runtime
from naas_abi_core.engine.nats_auth import ServiceTokenSource
from naas_abi_core.engine.nats_naming import connection_name
from naas_abi_core.services.tool_registry.adapters.tool_registry_nats_codec import (
    MAX_QUERY_CHARS,
    filter_to_pb,
    listing_from_pb,
    result_from_pb,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    MAX_CATALOG_LIST_LIMIT,
    MAX_CATALOG_SEARCH_LIMIT,
    IToolCatalogPort,
    ToolCatalogError,
    ToolCatalogRequestError,
    ToolCatalogSearch,
    ToolFilter,
    ToolListing,
    ToolNotFoundError,
    ToolRegistryError,
    ToolSearchUnavailableError,
)
from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb
from naas_abi_sdk.tool_registry import ToolRegistryClient
from naas_abi_sdk.transport import RPCError, Transport
from nats.errors import Error as NATSError

# Listing pages to read before giving up: a catalog this large is not one a
# process should hold in memory.
MAX_LIST_PAGES = 100


class ToolRegistrySecondaryAdapterNATSClient(IToolCatalogPort):
    def __init__(
        self,
        url: str,
        secret: str,
        identity: str = "engine",
        *,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self._connection = (url, secret, identity)
        self._transport: Transport | None = None
        self._remote: ToolRegistryClient | None = None
        self._lock = threading.Lock()

    @property
    def remote(self) -> ToolRegistryClient:
        with self._lock:
            if self._remote is None:
                url, secret, identity = self._connection
                self._transport = Transport(
                    url,
                    ServiceTokenSource(identity, secret),
                    timeout=self.timeout_seconds,
                    name=connection_name("abi-engine:tool_registry"),
                )
                self._remote = ToolRegistryClient(self._transport)
            return self._remote

    @remote.setter
    def remote(self, client: ToolRegistryClient) -> None:
        self._remote = client

    def _call(self, coroutine, ref: str = ""):
        try:
            return nats_runtime.run_coro(coroutine, timeout=self.timeout_seconds + 5)
        except RPCError as exc:
            if exc.code == "TOOL_NOT_FOUND":
                raise ToolNotFoundError(
                    f"No published tool matches '{ref}'. Check the module publishing "
                    "it is enabled, and the reference's namespace, name and version."
                ) from exc
            if exc.code == "SEARCH_UNAVAILABLE":
                raise ToolSearchUnavailableError(
                    "The serving engine has no embedding model or index for tool search."
                ) from exc
            if exc.code == "INVALID_ARGUMENT":
                raise ToolCatalogRequestError(
                    f"The serving engine's tool catalog refused the request: {exc}"
                ) from exc
            raise ToolCatalogError(
                f"The serving engine's tool catalog failed: {exc}"
            ) from exc
        except TimeoutError as exc:
            raise ToolCatalogError(
                "The serving engine's tool catalog did not answer in "
                f"{self.timeout_seconds:g} seconds."
            ) from exc
        except (NATSError, OSError) as exc:
            # Nobody answering (NoRespondersError), a closed or unreachable
            # connection: the serving engine is away, fenced or mid-handover.
            raise ToolCatalogError(
                f"The serving engine's tool catalog is unreachable: {type(exc).__name__}"
            ) from exc

    def list_tools(self, filter: ToolFilter | None = None) -> list[ToolListing]:
        listings: list[ToolListing] = []
        after = ""
        for _ in range(MAX_LIST_PAGES):
            page = self._call(
                self.remote.list_tools(
                    pb.ListToolsRequest(
                        filter=filter_to_pb(filter),
                        limit=MAX_CATALOG_LIST_LIMIT,
                        after=after,
                    )
                )
            )
            for tool in page.tools:
                try:
                    listings.append(listing_from_pb(tool))
                except ToolRegistryError as exc:
                    # One bad definition must not hide the catalog.
                    logger.warning(f"Tool registry: skipped a catalog entry: {exc}")
            if not page.next_after:
                return listings
            after = page.next_after
        raise ToolCatalogError(
            f"The tool catalog has more than {MAX_LIST_PAGES * MAX_CATALOG_LIST_LIMIT} tools"
        )

    def get_tool(self, ref: str) -> ToolListing:
        response = self._call(self.remote.get_tool(pb.GetToolRequest(ref=ref)), ref)
        return listing_from_pb(response.tool)

    def search_tools(
        self,
        query: str,
        limit: int,
        min_score: float | None = None,
        filter: ToolFilter | None = None,
    ) -> ToolCatalogSearch:
        # What the catalog accepts: a model-written query may be blank or long,
        # which a registry without a catalog never refused.
        query = query.strip()[:MAX_QUERY_CHARS].strip()
        if not query:
            return ToolCatalogSearch()
        request = pb.SearchToolsRequest(
            query=query,
            limit=min(limit, MAX_CATALOG_SEARCH_LIMIT),
            filter=filter_to_pb(filter),
        )
        if min_score is not None:
            request.min_score = min_score
        response = self._call(self.remote.search_tools(request))
        results = []
        for match in response.matches:
            try:
                results.append(result_from_pb(match))
            except ToolRegistryError as exc:
                logger.warning(f"Tool registry: skipped a catalog match: {exc}")
        return ToolCatalogSearch(results=tuple(results), truncated=response.truncated)

    def close(self) -> None:
        transport, self._transport = self._transport, None
        if transport is not None:
            nats_runtime.run_coro(transport.close())
