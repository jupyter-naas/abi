"""Reads the serving engine's tool catalog over NATS (``IToolCatalogPort``).

For an engine that does not serve (a client or a standby engine): its own
``ToolRegistryService`` publishes and resolves locally and reads the catalog
through this client (``configure_catalog``). Calls are read only, as the engine's
own process (a first-party identity), so the serving engine shows them every
tool; the registry then applies its caller's scopes to what comes back.
"""

from __future__ import annotations

from naas_abi_core.engine import nats_runtime
from naas_abi_core.engine.nats_auth import ServiceTokenSource
from naas_abi_core.engine.nats_naming import connection_name
from naas_abi_core.services.tool_registry.adapters.tool_registry_nats_codec import (
    filter_to_pb,
    listing_from_pb,
    result_from_pb,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    MAX_CATALOG_LIST_LIMIT,
    MAX_CATALOG_SEARCH_LIMIT,
    IToolCatalogPort,
    ToolFilter,
    ToolListing,
    ToolNotFoundError,
    ToolRegistryError,
    ToolSearchResult,
    ToolSearchUnavailableError,
)
from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb
from naas_abi_sdk.tool_registry import ToolRegistryClient
from naas_abi_sdk.transport import RPCError, Transport

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
        self.transport = Transport(
            url,
            ServiceTokenSource(identity, secret),
            timeout=timeout_seconds,
            name=connection_name("abi-engine:tool_registry"),
        )
        self.remote = ToolRegistryClient(self.transport)

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
                raise ValueError(str(exc)) from exc
            raise ToolRegistryError(
                f"The serving engine's tool catalog failed: {exc}"
            ) from exc
        except TimeoutError as exc:
            raise ToolRegistryError(
                "The serving engine's tool catalog did not answer in "
                f"{self.timeout_seconds:g} seconds."
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
            listings.extend(listing_from_pb(tool) for tool in page.tools)
            if not page.next_after:
                return listings
            after = page.next_after
        raise ToolRegistryError(
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
    ) -> list[ToolSearchResult]:
        request = pb.SearchToolsRequest(
            query=query,
            limit=min(limit, MAX_CATALOG_SEARCH_LIMIT),
            filter=filter_to_pb(filter),
        )
        if min_score is not None:
            request.min_score = min_score
        response = self._call(self.remote.search_tools(request))
        return [result_from_pb(match) for match in response.matches]

    def close(self) -> None:
        nats_runtime.run_coro(self.transport.close())
