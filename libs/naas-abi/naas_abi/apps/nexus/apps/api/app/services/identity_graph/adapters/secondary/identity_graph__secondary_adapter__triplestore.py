from __future__ import annotations

from collections.abc import Callable

from naas_abi.apps.nexus.apps.api.app.services.identity_graph.port import (
    IdentityGraphStorePort,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import Graph, URIRef


class IdentityGraphStoreSecondaryAdapterTripleStore(IdentityGraphStorePort):
    """Rebuilds the identity named graph: drop, then insert.

    Dropping first is what drops users and memberships deleted in Postgres
    since the last boot. ``DROP SILENT`` is a no-op if the graph is missing,
    and avoids ``list_graphs()`` + ``CLEAR GRAPH``: Fuseki's catalog can list a
    named graph that ``CLEAR GRAPH`` then rejects with HTTP 400.
    """

    def __init__(self, triple_store_getter: Callable[[], TripleStoreService]):
        self._triple_store_getter = triple_store_getter

    def replace_graph(self, graph_uri: URIRef, graph: Graph) -> None:
        triple_store = self._triple_store_getter()
        triple_store.query(f"DROP SILENT GRAPH <{graph_uri}>")
        if len(graph):
            triple_store.insert(graph, graph_uri)
