"""Workspace graph authorization. No HTTP, database or engine dependencies."""

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
from naas_abi.apps.nexus.graph_policy_config import (
    NEXUS_GRAPH,
    SCHEMA_GRAPH,
    WorkspaceGraphPolicyConfig,
)

OWNER_PREDICATE = "http://ontology.naas.ai/nexus/graphWorkspaceId"


@dataclass(frozen=True)
class GraphAccessScope:
    workspace_id: str
    readable: frozenset[str]
    writable: frozenset[str]
    allow_create: bool = False

    @classmethod
    def resolve(
        cls,
        workspace_id: str,
        config: WorkspaceGraphPolicyConfig,
        owned: set[str],
        role: str,
        *,
        catalog: set[str] | None = None,
    ) -> GraphAccessScope:
        owned = owned if config.include_owned else set()
        all_readable = (catalog or set()) if config.read_all else set()
        readable = (all_readable | set(config.read) | set(config.write) | owned) - {NEXUS_GRAPH}
        writer = role in {"owner", "admin", "member"}
        writable = ((set(config.write) | owned) - {NEXUS_GRAPH, SCHEMA_GRAPH}) if writer else set()
        return cls(
            workspace_id,
            frozenset(readable),
            frozenset(writable),
            config.allow_create and config.include_owned and writer,
        )

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
            raise GraphAccessError("Graph is not available with the required workspace permissions")


P = ParamSpec("P")
T = TypeVar("T")


def workspace_graph_operation(
    *,
    write: bool = False,
    create: bool = False,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Guard service entrypoints before queries, metadata access and cache reads."""

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
            if create and not scope.allow_create:
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
            return await method(*args, **kwargs)

        return guarded

    return decorate
