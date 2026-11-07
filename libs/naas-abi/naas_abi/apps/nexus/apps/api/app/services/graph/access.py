"""A workspace's view of the knowledge graphs. No HTTP or database dependencies.

Who may read or write a graph is the kernel's decision (IAM, by the workspace
IAM placed the graph in and the statements that share it). What stays here is
what the kernel cannot decide: which graphs *this workspace* offers its
members. A user who belongs to several workspaces holds rights to all their
graphs; each workspace's pages still list, query and cache only its own.
``GraphAccessScope`` is that view, already narrowed to what the kernel lets the
caller read (``readable``) and write (``writable``).
"""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphAccessError,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.sparql_safe import sparql_iri
from naas_abi_core.services.iam.IAMPorts import (
    PermissionDeniedError,
    ResourceNotFoundError,
)
from naas_abi_core.services.triple_store.TripleStorePorts import Exceptions

UNAVAILABLE = "Graph is not available with the required workspace permissions"


@dataclass(frozen=True)
class GraphAccessScope:
    workspace_id: str
    readable: frozenset[str]
    writable: frozenset[str]
    can_create: bool = False

    @property
    def cache_key(self) -> str:
        payload = [self.workspace_id, sorted(self.readable), sorted(self.writable)]
        return hashlib.sha256(json.dumps(payload).encode()).hexdigest()

    def require(
        self,
        workspace_id: str,
        graphs: list[str] | tuple[str, ...] = (),
        *,
        write: bool = False,
    ) -> None:
        if workspace_id != self.workspace_id:
            raise GraphAccessError("Graph request does not match the authorized workspace")
        for graph in graphs:
            sparql_iri(graph)
        if set(graphs) - (self.writable if write else self.readable):
            # Do not confirm whether an inaccessible graph actually exists.
            raise GraphAccessError(UNAVAILABLE)


P = ParamSpec("P")
T = TypeVar("T")


def workspace_graph_operation(
    *,
    write: bool = False,
    create: bool = False,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Guard service entrypoints before queries, metadata access and cache reads.

    The workspace's view is checked first; the kernel then decides every call
    on its own. What it refuses (a graph the caller may not see, or may not
    change) is a ``GraphAccessError`` here, as it is for the view.
    """

    def decorate(method: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        signature = inspect.signature(method)

        @wraps(method)
        async def guarded(*args: P.args, **kwargs: P.kwargs) -> T:
            values = signature.bind(*args, **kwargs).arguments
            scope: GraphAccessScope | None = values["self"].access_scope
            if scope is None:
                raise GraphAccessError("A workspace graph scope is required")
            graphs: list[str] = []
            for key in ("graph_uri", "graph_uris", "graph_names"):
                value = values.get(key)
                if isinstance(value, str):
                    graphs.append(value)
                elif value:
                    graphs.extend(value)
            scope.require(values["workspace_id"], graphs, write=write)
            if create and not scope.can_create:
                raise GraphAccessError("Graph creation is not allowed in this workspace")

            # Legacy discovery queries interpolate IRIs. Validate every URI-bearing
            # argument before it can become SPARQL syntax, including nested filters.
            def validate(name: str, value: Any) -> None:
                if isinstance(value, dict):
                    for k, v in value.items():
                        validate(k, v)
                elif isinstance(value, (tuple, list)):
                    for v in value:
                        validate(name, v)
                elif (
                    isinstance(value, str)
                    and value
                    and (name.endswith(("_uri", "_uris", "_iri", "_iris")) or name == "graph_names")
                ):
                    sparql_iri(value)

            for name, value in values.items():
                validate(name, value)
            try:
                return await method(*args, **kwargs)
            except (
                PermissionDeniedError,
                ResourceNotFoundError,
                Exceptions.GraphNotFoundError,
            ) as exc:
                raise GraphAccessError(UNAVAILABLE) from exc

        return guarded

    return decorate
