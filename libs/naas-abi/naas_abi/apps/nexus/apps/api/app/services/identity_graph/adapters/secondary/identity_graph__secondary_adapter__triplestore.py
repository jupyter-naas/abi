from __future__ import annotations

from collections.abc import Callable

from naas_abi.apps.nexus.apps.api.app.services.identity_graph.port import (
    IdentityGraphStorePort,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import Graph, URIRef


class IdentityGraphStoreSecondaryAdapterTripleStore(IdentityGraphStorePort):
    """Rebuilds the identity named graph: clear (or create), then insert.

    Clearing first is what drops users and memberships deleted in Postgres
    since the last boot.
    """

    def __init__(self, triple_store_getter: Callable[[], TripleStoreService]):
        self._triple_store_getter = triple_store_getter

    def replace_graph(self, graph_uri: URIRef, graph: Graph) -> None:
        triple_store = self._triple_store_getter()
        if graph_uri in triple_store.list_graphs():
            triple_store.clear_graph(graph_uri)
        else:
            triple_store.create_graph(graph_uri)
        if len(graph):
            triple_store.insert(graph, graph_uri)
