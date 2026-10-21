"""The serving engine's tool catalog over NATS, read only.

``abi.svc.tool_registry.v1.{list_tools,get_tool,search_tools}``, answered from the
registry of the process that serves, from what it holds itself (``list_local``,
``get_local``, ``search_local``): it never reads a catalog, so it cannot call
itself. Nothing here resolves a binding, builds a tool or sends a configuration
value, and ``ToolRegistryService.search_local`` ranks definitions without
touching their bindings.

Who is asking is the verified service identity (``Nats-Auth-Token``), never the
request: the scopes a caller discovers with come from ``caller_context``. The
engine's own processes hold every scope (they apply their users' scopes
themselves, see ``ToolRegistryService.search_tools`` on a client engine); an SDK
module holds the scopes configured for its identity (``nats.tool_registry.
module_scopes``), by default none. The request's ``CallContext`` is not read, and
a tool the caller may not discover is reported as not found.

Requests are validated here, on the server, against the limits in
``tool_registry_nats_codec`` (the contract's Protovalidate rules, written out):
the same approach as the other kernel services. A reply is kept under half the
broker's limit, so it never needs RPC overflow: a page or a result list ends at
the tool that would pass it, and a single definition above it is neither listed
nor returned.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from functools import partial
from typing import Any

import nats
from google.protobuf.message import DecodeError
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import (
    FIRST_PARTY_IDENTITIES,
    InvalidServiceTokenError,
    verify_service_token,
)
from naas_abi_core.engine.nats_dispatch import DomainRPCDispatcher
from naas_abi_core.engine.nats_rpc import (
    RequestPayloadError,
    broker_limit,
    request_payload,
    respond_protobuf,
)
from naas_abi_core.engine.nats_sessions import ServicePrimary
from naas_abi_core.engine.nats_tracing import TracedService, add_traced_service
from naas_abi_core.services.tool_registry.adapters.tool_registry_nats_codec import (
    DEFAULT_LIST_LIMIT,
    DEFAULT_SEARCH_LIMIT,
    MAX_AFTER_CHARS,
    MAX_QUERY_CHARS,
    MAX_REF_CHARS,
    OPERATIONS,
    SERVICE_NAME,
    SERVICE_VERSION,
    SUBJECT_PREFIX,
    entry_to_pb,
    filter_from_pb,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    MAX_CATALOG_LIST_LIMIT,
    MAX_CATALOG_SEARCH_LIMIT,
    ToolContext,
    ToolListing,
    ToolNotFoundError,
    ToolRef,
    ToolRegistryError,
    ToolSearchUnavailableError,
)
from naas_abi_core.services.tool_registry.ToolRegistryService import (
    ToolRegistryService,
)
from naas_abi_proto.common.v1 import common_pb2
from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb

__all__ = ["SUBJECT_PREFIX", "ToolRegistryPrimaryAdapterNATS"]

# A reply stays under this share of the broker's limit (1 MiB when unknown).
REPLY_SHARE = 2
DEFAULT_BROKER_LIMIT = 1024 * 1024
_MESSAGES = {
    "list_tools": "ListTools",
    "get_tool": "GetTool",
    "search_tools": "SearchTools",
}


class _Invalid(ValueError):
    """A request outside the contract's limits; its message is safe to return."""


class ToolRegistryPrimaryAdapterNATS(ServicePrimary):
    def __init__(
        self,
        registry: ToolRegistryService,
        jwt_secret: str,
        *,
        module_scopes: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        self._registry = registry
        self._jwt_secret = jwt_secret
        self._module_scopes = {
            identity: frozenset(scopes)
            for identity, scopes in (module_scopes or {}).items()
        }
        self._dispatch = DomainRPCDispatcher(SERVICE_NAME)
        self._service: TracedService | None = None

    async def start(self, nc: nats.NATS) -> None:
        if self._service is not None:
            return
        service = await add_traced_service(
            nc,
            name=SERVICE_NAME,
            version=SERVICE_VERSION,
            description="ABI tool catalog (read only), exposed over NATS RPC (v1).",
        )
        self._service = service
        for operation in OPERATIONS:
            await service.add_endpoint(
                name=operation,
                subject=f"{SUBJECT_PREFIX}.{operation}",
                handler=partial(self._handle, operation=operation),
            )

    def caller_context(self, identity: str) -> ToolContext:
        """The context a verified ``identity`` discovers tools with.

        Only the identity decides it: first-party processes hold every scope the
        catalog's tools require, a module those configured for it."""
        if identity in FIRST_PARTY_IDENTITIES:
            scopes = self._registry.known_scopes()
        else:
            scopes = set(self._module_scopes.get(identity, ()))
        return ToolContext(scopes=frozenset(scopes))

    async def _handle(self, request, *, operation: str) -> None:
        response_type = getattr(pb, _MESSAGES[operation] + "Response")
        try:
            identity = verify_service_token(
                (request.headers or {}).get("Nats-Auth-Token", ""), self._jwt_secret
            )
        except InvalidServiceTokenError:
            await self._fail(
                request,
                response_type,
                "UNAUTHENTICATED",
                "missing or invalid auth token",
            )
            return
        try:
            parsed = getattr(pb, _MESSAGES[operation] + "Request").FromString(
                await request_payload(request)
            )
            budget = (broker_limit(request) or DEFAULT_BROKER_LIMIT) // REPLY_SHARE
            result = await self._dispatch.call(
                partial(self._call, operation, identity, budget), parsed
            )
        except RequestPayloadError as exc:
            await self._fail(request, response_type, exc.code, exc.message)
            return
        except DecodeError:
            await self._fail(
                request, response_type, "INVALID_ARGUMENT", "invalid protobuf request"
            )
            return
        except _Invalid as exc:
            await self._fail(request, response_type, "INVALID_ARGUMENT", str(exc))
            return
        except ToolNotFoundError:
            await self._fail(
                request, response_type, "TOOL_NOT_FOUND", "no visible tool matches"
            )
            return
        except ToolSearchUnavailableError:
            await self._fail(
                request,
                response_type,
                "SEARCH_UNAVAILABLE",
                "tool search has no embedding model or index here",
            )
            return
        except Exception as exc:  # noqa: BLE001 - translate failures at the RPC boundary
            # Embedding providers and index backends may put credentials in theirs.
            logger.warning(
                f"tool_registry NATS {operation} failed: {type(exc).__name__}"
            )
            await self._fail(request, response_type, "INTERNAL", "internal error")
            return
        await respond_protobuf(request, result, response_type)

    @staticmethod
    async def _fail(request, response_type, code: str, message: str) -> None:
        await respond_protobuf(
            request,
            response_type(
                error=common_pb2.CallError(code=code, message=message, retryable=False)
            ),
            response_type,
        )

    def _call(self, operation: str, identity: str, budget: int, request: Any):
        context = self.caller_context(identity)
        if operation == "get_tool":
            return self._get_tool(context, budget, request)
        if operation == "list_tools":
            return self._list_tools(context, budget, request)
        return self._search_tools(context, budget, request)

    # ------------------------------------------------------------- operations
    def _get_tool(self, context, budget, request: pb.GetToolRequest):
        if not request.ref or len(request.ref) > MAX_REF_CHARS:
            raise _Invalid(f"ref must be 1..{MAX_REF_CHARS} characters")
        try:
            ref = ToolRef.parse(request.ref)
        except ToolRegistryError as exc:
            raise _Invalid(str(exc)) from exc
        entry = self._encode(self._registry.get_local(ref, context), budget)
        if entry is None:
            raise _Invalid("the tool definition is too large to send")
        return pb.GetToolResponse(tool=entry)

    def _list_tools(self, context, budget, request: pb.ListToolsRequest):
        limit = request.limit or DEFAULT_LIST_LIMIT
        if not 1 <= limit <= MAX_CATALOG_LIST_LIMIT:
            raise _Invalid(f"limit must be 1..{MAX_CATALOG_LIST_LIMIT}")
        if len(request.after) > MAX_AFTER_CHARS:
            raise _Invalid("after is too long")
        listings = [
            listing
            for listing in self._registry.list_local(
                context, self._filter(request.filter)
            )
            if str(listing.definition.id) > request.after
        ]
        response = pb.ListToolsResponse()
        used = 0
        for listing in listings:
            if len(response.tools) >= limit:
                response.next_after = response.tools[-1].definition.id
                break
            entry = self._encode(listing, budget)
            if entry is None:
                continue
            used += entry.ByteSize()
            if used > budget and response.tools:
                response.next_after = response.tools[-1].definition.id
                break
            response.tools.append(entry)
        return response

    def _search_tools(self, context, budget, request: pb.SearchToolsRequest):
        query = request.query
        if not query.strip() or len(query) > MAX_QUERY_CHARS:
            raise _Invalid(f"query must be 1..{MAX_QUERY_CHARS} characters")
        limit = request.limit or DEFAULT_SEARCH_LIMIT
        if not 1 <= limit <= MAX_CATALOG_SEARCH_LIMIT:
            raise _Invalid(f"limit must be 1..{MAX_CATALOG_SEARCH_LIMIT}")
        min_score = request.min_score if request.HasField("min_score") else None
        if min_score is not None and not math.isfinite(min_score):
            raise _Invalid("min_score must be finite")
        results = self._registry.search_local(
            query,
            context,
            limit=limit,
            min_score=min_score,
            filter=self._filter(request.filter),
        )
        response = pb.SearchToolsResponse()
        used = 0
        for result in results:
            entry = self._encode(
                ToolListing(
                    definition=result.definition, availability=result.availability
                ),
                budget,
            )
            if entry is None:
                # Not served (JSON cannot carry it, or it alone passes the budget):
                # a larger limit reaches the matches after it.
                response.truncated = True
                continue
            match = pb.ToolMatch(tool=entry, score=result.score)
            if used + match.ByteSize() > budget:
                # Past the budget: what follows is cut, whatever the limit.
                response.truncated = True
                break
            used += match.ByteSize()
            response.matches.append(match)
        return response

    @staticmethod
    def _filter(message: pb.ToolFilter):
        try:
            return filter_from_pb(message)
        except ValueError as exc:
            raise _Invalid(str(exc)) from exc

    @staticmethod
    def _encode(listing, budget: int) -> pb.ToolEntry | None:
        """The entry, or None when its definition cannot be sent (JSON cannot carry
        it, or it alone passes the reply budget)."""
        try:
            entry = entry_to_pb(listing)
        except (ValueError, TypeError):
            logger.warning(
                f"tool_registry NATS: '{listing.definition.id}' has a definition "
                "JSON cannot carry; not served"
            )
            return None
        if entry.ByteSize() > budget:
            logger.warning(
                f"tool_registry NATS: '{listing.definition.id}' has a definition "
                f"above {budget} bytes; not served"
            )
            return None
        return entry
